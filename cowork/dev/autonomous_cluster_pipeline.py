#!/usr/bin/env python3
"""JARVIS Autonomous Cluster Pipeline — Non-stop distributed work.

Orchestrates continuous task execution across all available cluster nodes.
Adapts dynamically: uses whatever nodes are online, skips dead ones.

Usage:
    python cowork/dev/autonomous_cluster_pipeline.py --cycles 1000
    python cowork/dev/autonomous_cluster_pipeline.py --cycles 0      # infinite
    python cowork/dev/autonomous_cluster_pipeline.py --status
"""
import io
import json
import os
import random
import sqlite3
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# UTF-8 handled via PYTHONUTF8=1 env or --log file

from _paths import TURBO_DIR as TURBO
DB_PATH = TURBO / "data" / "cluster_pipeline.db"
PID_FILE = TURBO / "data" / "cluster_pipeline.pid"

TELEGRAM_CHAT = "2010747443"

# ── Node Registry ────────────────────────────────────────────

NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "model": "qwen3-8b",
        "prefix": "/nothink\n",
        "max_tokens": 1024,
        "timeout": 180,
        "type": "lmstudio",
        "role": "fast",  # Pattern detection, code gen
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek/deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "timeout": 90,
        "type": "lmstudio",
        "role": "deep",  # Deep reasoning, backtesting
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "deepseek/deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "timeout": 180,
        "type": "lmstudio",
        "role": "deep",
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "timeout": 45,
        "type": "ollama",
        "role": "excluded",  # 8% success — excluded from routing
    },
}

# ── Node Health State ────────────────────────────────────────

node_health = {}  # node_name -> {"alive": bool, "last_check": float, "fails": int, "latency": float}


def check_node(name):
    """Quick ping a node. Returns (alive, latency_ms)."""
    node = NODES[name]
    t0 = time.time()
    try:
        if node["type"] == "ollama":
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": False, "think": False
            }).encode()
            d = _http_post(node["url"], body, 10)
            ok = "message" in d
        else:
            body = json.dumps({
                "model": node["model"],
                "input": node.get("prefix", "") + "Hi",
                "temperature": 0.1, "max_output_tokens": 5,
                "stream": False, "store": False
            }).encode()
            d = _http_post(node["url"], body, 15)
            ok = "output" in d
        latency = (time.time() - t0) * 1000
        return ok, latency
    except Exception:
        return False, (time.time() - t0) * 1000


def health_check_all():
    """Check all nodes in parallel, update health state."""
    print("[HEALTH] Checking cluster nodes...")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(check_node, n): n for n in NODES}
        for f in as_completed(futs):
            name = futs[f]
            alive, lat = f.result()
            prev = node_health.get(name, {})
            fails = 0 if alive else prev.get("fails", 0) + 1
            node_health[name] = {
                "alive": alive, "last_check": time.time(),
                "fails": fails, "latency": lat
            }
            status = f"OK ({lat:.0f}ms)" if alive else f"DOWN (fails={fails})"
            print(f"  {name:10s} [{NODES[name]['role']:8s}] {status}")

    online = [n for n, h in node_health.items() if h["alive"]]
    print(f"  => {len(online)}/{len(NODES)} nodes online: {', '.join(online)}", flush=True)
    return online


def get_alive_nodes():
    """Return list of alive node names, with circuit breaker (skip if 3+ fails)."""
    alive = []
    for name, h in node_health.items():
        if NODES[name]["role"] == "excluded":
            continue
        if h.get("alive") and h.get("fails", 0) < 3:
            alive.append(name)
    return alive if alive else ["M1"]  # fallback — M1 always local


# ── Query Functions ──────────────────────────────────────────

def _http_post(url, body_bytes, timeout_s):
    """HTTP POST using urllib (no subprocess, no curl)."""
    import urllib.request
    req = urllib.request.Request(
        url, data=body_bytes,
        headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout_s)
    return json.loads(resp.read().decode("utf-8", "replace"))


def query_node(name, prompt):
    """Query a node. Returns (response_text, elapsed_s, error)."""
    node = NODES[name]
    timeout = node["timeout"]
    t0 = time.time()
    try:
        if node["type"] == "ollama":
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False
            }).encode()
            d = _http_post(node["url"], body, timeout)
            text = d.get("message", {}).get("content", "").strip()
        else:
            body = json.dumps({
                "model": node["model"],
                "input": node.get("prefix", "") + prompt,
                "temperature": 0.2,
                "max_output_tokens": node.get("max_tokens", 1024),
                "stream": False, "store": False
            }).encode()
            d = _http_post(node["url"], body, timeout)
            text = ""
            # Try message block first, fallback to reasoning (deepseek-r1)
            for item in reversed(d.get("output", [])):
                if item.get("type") == "message":
                    c = item.get("content", "")
                    text = c.strip() if isinstance(c, str) else str(c)
                    break
            if not text:
                for item in d.get("output", []):
                    if item.get("type") == "reasoning":
                        c = item.get("content", "")
                        text = c.strip() if isinstance(c, str) else str(c)
                        break

        elapsed = time.time() - t0
        if text:
            node_health[name]["fails"] = 0
            return text, elapsed, None
        else:
            node_health[name]["fails"] = node_health.get(name, {}).get("fails", 0) + 1
            return None, elapsed, "empty response"
    except Exception as e:
        elapsed = time.time() - t0
        node_health.setdefault(name, {})["fails"] = node_health.get(name, {}).get("fails", 0) + 1
        return None, elapsed, str(e)[:120]


# ── Task Bank (185+ taches) ──────────────────────────────────

TASK_CATEGORIES = {
    "TRADING": [
        # Original 10
        "Analyse technique BTC/USDT 1min: quels indicateurs donneraient le meilleur signal d'entree maintenant? RSI, MACD, BB, VWAP. Reponds avec signal LONG/SHORT/NEUTRE et justification en 3 lignes.",
        "Propose un set de 5 regles de filtrage pour eviter les faux signaux en scalping crypto. Chaque regle avec condition precise et seuil numerique.",
        "Compare Grid Trading vs DCA vs Momentum vs Mean Reversion pour BTC scalping 10x levier. Tableau: winrate, drawdown, sharpe attendu.",
        "Ecris une fonction Python qui calcule le Sharpe Ratio, Sortino Ratio et Max Drawdown a partir d'une liste de PnL. Code complet.",
        "Propose un systeme de scoring multi-facteurs (0-100) pour evaluer un signal de trading crypto. 8 facteurs avec poids.",
        "Quels sont les 5 patterns de chandelier les plus fiables en scalping crypto 1min? Taux de reussite attendu pour chaque.",
        "Comment detecter un squeeze de Bollinger Bands et l'exploiter en scalping? Conditions d'entree, TP, SL precis.",
        "Propose une strategie de hedging pour un bot crypto avec 2 positions simultanees (long+short). Conditions et sizing.",
        "Ecris un algorithme de trailing stop loss adaptatif basé sur l'ATR. Python, 20 lignes max.",
        "Compare les exchanges MEXC vs Binance vs Bybit pour le scalping futures. Latence, frais, liquidite.",
        # New 10
        "Ecris une fonction Python qui detecte les divergences RSI (bullish et bearish) sur un DataFrame OHLCV. Code complet avec detection de pics/creux.",
        "Propose un systeme de gestion de risque pour un portefeuille de 10 paires crypto futures. Max drawdown par paire, correlation matrix, position sizing dynamique.",
        "Ecris un backtester Python minimaliste (50 lignes) qui teste une strategie mean-reversion sur des donnees OHLCV 1min. Avec calcul du PnL et metrics.",
        "Comment implementer un order book imbalance detector en Python? Ratio bid/ask, seuils d'alerte, code fonctionnel.",
        "Propose une strategie de market making pour un bot crypto: spread dynamique, inventory management, risk limits. Pseudo-code detaille.",
        "Ecris un detecteur de pump & dump en Python: volume spike + price deviation + time window. Retourne alerte avec score de confiance.",
        "Compare les methodes de calcul de volatilite: historical, Parkinson, Garman-Klass, Yang-Zhang. Formules et implementation Python.",
        "Ecris un module Python de gestion multi-timeframe: agregation 1min→5min→15min→1h, avec signaux alignes. Code complet.",
        "Propose un systeme de liquidite scoring pour filtrer les paires crypto tradables: spread, depth, volume 24h, slippage estimation.",
        "Ecris une classe Python FundingRateTracker qui collecte les funding rates de 5 exchanges et detecte les opportunites d'arbitrage. Code complet.",
    ],
    "CODE": [
        # Original 10
        "Ecris une classe Python AsyncTaskQueue avec priority, max_workers, et timeout par task. Code complet avec asyncio.",
        "Ecris un rate limiter Python thread-safe avec sliding window algorithm. Code complet.",
        "Ecris un decorator Python @circuit_breaker(threshold=5, timeout=60) qui gere les pannes de service. Code complet.",
        "Ecris un pipeline de donnees Python avec 4 stages: fetch→validate→transform→store. Pattern pipeline avec generators.",
        "Ecris un serveur HTTP healthcheck Python en 30 lignes qui expose /health, /ready, /metrics pour un cluster.",
        "Ecris une classe Python ConnectionPool avec max_size, min_idle, et health_check periodique. Code complet.",
        "Ecris un logger Python structure (JSON) avec rotation, niveaux, et context managers. Code complet.",
        "Ecris un cache LRU distribue avec invalidation par TTL et event-driven updates. Python, code complet.",
        "Ecris un router HTTP Python minimal qui dispatche GET/POST vers des handlers avec pattern matching. 40 lignes.",
        "Ecris un system monitor Python qui collecte CPU, RAM, GPU temp et ecrit dans SQLite toutes les 10s. Code complet.",
        # New 10
        "Ecris un event emitter Python type-safe avec subscribe, unsubscribe, emit et wildcards. Support async handlers. Code complet.",
        "Ecris un retry decorator Python avec backoff exponentiel, jitter, et liste d'exceptions retryable. @retry(max=5, backoff=2.0). Code complet.",
        "Ecris un state machine Python generique avec transitions, guards, et callbacks on_enter/on_exit. Code complet avec exemple.",
        "Ecris un plugin loader Python dynamique qui scanne un dossier, importe les modules, et enregistre les classes decorees @plugin. Code complet.",
        "Ecris un diff engine Python qui compare deux dicts imbriques et retourne les changements (added, removed, modified) avec chemins JSON. Code complet.",
        "Ecris un command pattern Python avec undo/redo stack, macro recording, et serialisation JSON. Code complet.",
        "Ecris un thread pool Python custom avec work stealing, task priorities, et graceful shutdown. Code complet sans concurrent.futures.",
        "Ecris un schema validator Python qui valide un dict contre un schema (types, required, ranges, patterns) sans lib externe. Code complet.",
        "Ecris un pub/sub broker Python in-process avec topics, filtres, et dead letter queue. Thread-safe. Code complet.",
        "Ecris un file watcher Python cross-platform qui detecte create/modify/delete et appelle des callbacks. Polling + hash. Code complet.",
    ],
    "ARCHITECTURE": [
        # Original 5
        "Propose un schema d'architecture pour un bot de trading crypto autonome avec 4 composants: data, strategy, execution, monitoring. Diagramme texte.",
        "Comment decomposer un monolithe Python de 6000 lignes en microservices? Plan en 5 etapes avec criteres de decoupe.",
        "Propose un pattern de communication inter-agents pour un cluster IA de 4 noeuds. Compare REST vs gRPC vs message queue.",
        "Quels sont les 5 principes SOLID appliques a un orchestrateur multi-agent IA? Un exemple concret par principe.",
        "Propose une architecture event-driven pour un systeme de trading avec event sourcing. Schema + composants.",
        # New 7
        "Propose une architecture hexagonale (ports & adapters) pour un service de dispatch IA multi-noeuds. Diagramme + interfaces Python.",
        "Compare CQRS vs CRUD pour un systeme de trading avec historique de 10M+ trades. Avantages, complexite, schema de donnees.",
        "Propose un design pattern pour un pipeline de traitement GPU avec failover automatique entre 4 GPU heterogenes. Diagramme + pseudo-code.",
        "Comment concevoir un systeme de cache multi-niveaux (L1 in-process, L2 Redis, L3 disk) pour un cluster IA? Invalidation et coherence.",
        "Propose une architecture de plugin pour etendre un orchestrateur IA sans modifier le core. Interface, discovery, lifecycle. Code Python.",
        "Compare les patterns Saga vs 2PC pour coordonner des transactions distribuees dans un cluster IA multi-noeuds. Pros/cons + pseudo-code.",
        "Propose un schema d'architecture pour un data lake temps-reel qui ingere des donnees de 10 exchanges crypto + sentiment social. Pipeline + stockage + query.",
    ],
    "SECURITY": [
        # Original 4
        "Audite un cluster IA local avec 4 machines sur LAN: tokens en clair, API sans auth, SQLite non chiffre. Top 10 fixes urgents.",
        "Ecris un scanner de securite Python qui detecte: hardcoded tokens, SQL injection patterns, imports dangereux dans un projet. Code complet.",
        "Compare les strategies d'authentification pour un cluster IA local: mTLS vs API keys vs JWT. Pros/cons.",
        "Propose un plan de hardening pour un serveur Windows qui heberge LM Studio avec GPU. 10 actions concretes.",
        # New 6
        "Ecris un module Python de chiffrement AES-256-GCM pour proteger les API keys dans un fichier config. Encrypt/decrypt avec derive de cle PBKDF2. Code complet.",
        "Propose un systeme de rate limiting et IP banning pour proteger un cluster IA expose sur LAN. Regles iptables + code Python.",
        "Ecris un audit logger Python qui enregistre chaque acces API avec timestamp, IP, user, action, et genere des alertes sur patterns suspects. Code complet.",
        "Comment implementer un sandboxing pour l'execution de code genere par LLM? Compare subprocess, Docker, nsjail. Avec code Python d'exemple.",
        "Ecris un scanner de vulnerabilites Python pour les dependances pip: parse requirements.txt, check CVE via API OSV.dev. Code complet.",
        "Propose un modele de permissions RBAC pour un cluster IA multi-utilisateurs: roles (admin, operator, viewer), resources, policies. Schema + implementation Python.",
    ],
    "OPTIMIZATION": [
        # Original 5
        "Comment optimiser le throughput d'un cluster IA avec 4 noeuds de puissance inegale (8GB-46GB VRAM)? 5 strategies de load balancing.",
        "Ecris un profiler Python qui mesure le temps de chaque etape d'un pipeline de dispatch IA. Decorator + rapport. Code complet.",
        "Propose un algorithme de routing adaptatif qui apprend quel noeud est meilleur pour quel type de tache. Pseudo-code.",
        "Comment reduire la latence d'inference de 30s a 10s sur un modele 8B avec 6 GPU? 5 techniques concretes.",
        "Ecris un benchmark automatise Python qui teste 4 noeuds IA avec 10 prompts et classe par qualite/vitesse. Code complet.",
        # New 7
        "Ecris un memory profiler Python qui track les allocations par fonction et detecte les memory leaks. Decorator + rapport HTML. Code complet.",
        "Propose un algorithme de batching dynamique pour regrouper les requetes IA par taille et priorite. Minimiser la latence P99. Pseudo-code + implementation.",
        "Ecris un optimiseur de requetes SQLite Python qui analyse les EXPLAIN QUERY PLAN et suggere des index manquants. Code complet.",
        "Comment implementer le speculative decoding pour accelerer l'inference d'un LLM 8B avec un draft model 1.7B? Explication + pseudo-code.",
        "Ecris un garbage collector Python custom pour un cache avec politique ARC (Adaptive Replacement Cache). Code complet.",
        "Propose un systeme de prefetch intelligent qui predit les prochaines requetes IA et pre-charge les modeles. Algorithme + code Python.",
        "Ecris un compressor de prompts Python qui reduit la taille des prompts de 30% sans perte semantique. Techniques: dedup, abbreviation, structural compression. Code complet.",
    ],
    "LEARNING": [
        # Original 5
        "Compare few-shot, zero-shot et chain-of-thought pour la generation de code Python. Quel mode pour quel type de tache?",
        "Propose un systeme de scoring de qualite pour evaluer les reponses d'un LLM: 5 criteres quantitatifs avec formule.",
        "Comment fine-tuner un modele 8B avec QLoRA sur 1 GPU 12GB? Guide en 10 etapes avec hyperparametres.",
        "Ecris un evaluateur automatique de reponses IA en Python: compare output vs expected, score 0-100. Code complet.",
        "Propose 10 techniques de prompt engineering pour ameliorer la qualite de code genere par un LLM local.",
        # New 7
        "Ecris un generateur de dataset de fine-tuning Python qui extrait des paires (instruction, response) a partir de code source. Code complet.",
        "Compare les methodes de distillation de connaissances: logit matching, attention transfer, feature imitation. Tableau comparatif + pseudo-code.",
        "Propose un curriculum learning pipeline pour entrainer progressivement un LLM sur des taches de difficulte croissante. 5 niveaux avec criteres de graduation.",
        "Ecris un A/B testing framework Python pour comparer 2 modeles IA sur les memes prompts. Statistical significance, effect size, confidence interval. Code complet.",
        "Comment implementer le RLHF (Reinforcement Learning from Human Feedback) de facon simplifiee pour un modele 8B? Pipeline en 4 etapes.",
        "Ecris un systeme de feedback loop Python ou les reponses IA sont evaluees et les meilleurs exemples sont reinjectes dans le prompt. Code complet.",
        "Propose un benchmark personnalise pour evaluer un LLM local sur 5 dimensions: code, raisonnement, creativite, factualite, instruction following. 3 prompts par dimension.",
    ],
    "MATH": [
        # Original 5
        "Derive la formule du Kelly Criterion pour le dimensionnement de position en trading. Etapes completes.",
        "Calcule la probabilite de drawdown >20% pour un bot avec winrate 55% et ratio 1.5 apres 100 trades.",
        "Ecris un solver Python pour optimiser un portefeuille de 10 crypto selon Markowitz. Mean-variance avec contraintes.",
        "Modelise la volatilite BTC/1min avec un processus GARCH(1,1). Equations et implementation Python.",
        "Calcule l'Expected Shortfall (CVaR) a 95% pour une distribution de returns non-gaussienne. Formule et code.",
        # New 7
        "Ecris un Monte Carlo simulator Python pour estimer la probabilite de ruine d'un bot de trading avec 1000 simulations. Parametres: winrate, RR, bankroll, position size. Code complet.",
        "Derive et implemente la formule de Black-Scholes pour le pricing d'options crypto. Equations + code Python.",
        "Ecris un solver de programmation lineaire Python (simplex) pour optimiser l'allocation de GPU entre 4 noeuds et 6 types de taches. Code complet sans scipy.",
        "Calcule l'entropie de Shannon et l'information mutuelle entre les returns de BTC et ETH sur 1000 periodes. Formule + code Python.",
        "Ecris un filtre de Kalman en Python pour lisser une serie temporelle de prix crypto bruites. Equations + implementation complete.",
        "Modelise un processus de Poisson pour l'arrivee des ordres sur un carnet crypto. Lambda estimation + simulation Python.",
        "Ecris un algorithme de descente de gradient Python from scratch pour optimiser les poids d'un ensemble de signaux de trading. SGD + momentum + code complet.",
    ],
    # ── NEW CATEGORIES ──────────────────────────────────────────
    "CRYPTO_ANALYSIS": [
        "Ecris un analyseur de whale wallets Python qui track les top 10 addresses BTC et detecte les mouvements >100 BTC. API blockchain.info + alertes. Code complet.",
        "Propose un systeme de sentiment analysis crypto: sources (Twitter, Reddit, Fear&Greed), scoring (-100 a +100), correlation avec prix. Pipeline Python.",
        "Ecris un detecteur de correlation dynamique Python entre 10 cryptos: rolling correlation matrix, heatmap, breakout detection. Code complet avec numpy.",
        "Comment analyser la liquidite d'un order book crypto? Metrics: bid-ask spread, depth ratio, resilience, slippage estimation. Code Python complet.",
        "Ecris un analyseur de funding rates multi-exchange Python: collecte Binance+Bybit+MEXC, detection d'anomalies, signal long/short. Code complet.",
        "Propose un systeme d'analyse on-chain pour ETH: gas tracker, active addresses, exchange inflows/outflows. Architecture + code Python.",
        "Ecris un scanner de patterns harmoniques Python (Gartley, Butterfly, Bat, Crab) sur des donnees OHLCV. Detection automatique + scoring. Code complet.",
        "Propose un algorithme de detection de regime de marche (trending, ranging, volatile) base sur ADX + ATR + volume. Code Python avec state machine.",
        "Ecris un analyseur de dominance BTC Python: calcul de dominance, correlation avec altseason, signaux de rotation. Code complet.",
        "Comment construire un index de fear & greed crypto custom avec 6 inputs: volatilite, volume, social, dominance, trends, momentum? Formule + code Python.",
        "Ecris un tracker de liquidations crypto Python: websocket Binance, aggregation par timeframe, detection de cascades. Code complet.",
        "Propose un systeme de scoring de tokenomics pour evaluer un projet crypto: supply, inflation, vesting, utility. 10 criteres avec formule. Code Python.",
        "Ecris un detecteur d'arbitrage triangulaire Python pour 3 paires crypto sur un exchange. Detection + calcul profit net apres fees. Code complet.",
        "Propose un modele de prediction de volatilite crypto base sur les options et le VIX crypto. Formule + implementation Python.",
        "Ecris un analyseur de mempool BTC Python: taille, fee estimation, detection de transactions suspectes. Code complet avec API mempool.space.",
    ],
    "PYTHON_ADVANCED": [
        "Ecris un decorator Python @memoize qui supporte les arguments hashables et non-hashables (listes, dicts) avec un fallback pickle. Code complet avec tests.",
        "Ecris une metaclasse Python SingletonMeta qui garantit une seule instance par classe, thread-safe, avec reset pour les tests. Code complet.",
        "Ecris un async context manager Python pour gerer un pool de connexions avec acquire/release, timeout, et health check. Code complet avec asyncio.",
        "Ecris un generator Python infini qui produit des nombres de Fibonacci avec support send() pour reset et throw() pour skip. Code complet.",
        "Ecris un descriptor Python TypedField qui valide le type, la plage, et le pattern regex a l'assignation. Code complet avec __set_name__.",
        "Ecris une metaclasse Python ABCRegistry qui enregistre automatiquement toutes les sous-classes et expose un factory method. Code complet.",
        "Ecris un async generator Python qui multiplex 3 sources de donnees (websocket, file, queue) avec priorite et backpressure. Code complet.",
        "Ecris un decorator Python @inject qui resout automatiquement les dependances via type hints (dependency injection simple). Code complet.",
        "Ecris un context manager Python TransactionScope qui supporte le nesting, rollback automatique, et savepoints. Code complet.",
        "Ecris une classe Python utilisant __init_subclass__ pour auto-enregistrer les handlers et __class_getitem__ pour le typing generique. Code complet.",
        "Ecris un protocol Python (PEP 544) avec runtime checkable pour definir une interface Dispatchable avec type checking. Code complet.",
        "Ecris un dataclass Python avance avec validation, serialisation JSON, diff entre instances, et merge. Code complet sans pydantic.",
        "Ecris un async semaphore Python adaptatif qui ajuste sa capacite en fonction de la latence observee. Code complet.",
        "Ecris un WeakValueDictionary Python custom avec callbacks on_expire et statistiques de hit/miss. Code complet.",
        "Ecris un module Python de pattern matching structurel (match/case) pour parser et transformer un AST simple. 5 cas d'usage. Code complet.",
    ],
    "DATABASE": [
        "Ecris un systeme de migration SQLite Python: versioning, up/down, rollback, dry-run. Stocke l'historique dans une table meta. Code complet.",
        "Ecris un query builder Python pour SQLite: SELECT, WHERE, JOIN, ORDER BY, LIMIT avec chainage fluent. Code complet sans ORM.",
        "Propose un schema d'indexation optimal pour une table de 10M trades crypto (timestamp, pair, price, volume, side). Benchmark avant/apres.",
        "Ecris un module Python de replication SQLite: master→replica avec WAL mode, sync periodique, conflict resolution. Code complet.",
        "Ecris un connection pool SQLite Python thread-safe avec max_connections, idle timeout, et health check. Code complet.",
        "Propose un schema de partitioning temporel pour une table de logs IA: 1 table par jour, rotation automatique, requetes cross-partition. Code Python.",
        "Ecris un ORM Python minimaliste pour SQLite: Model base class, Field types, auto CREATE TABLE, CRUD operations. 100 lignes max. Code complet.",
        "Ecris un systeme de backup incremental SQLite Python: full backup + WAL shipping, restore point-in-time. Code complet.",
        "Ecris un query optimizer Python qui analyse les slow queries SQLite (>100ms), suggere des index, et genere un rapport. Code complet.",
        "Ecris un data versioning system Python avec SQLite: chaque modification est versionnee, diff entre versions, restore. Code complet.",
    ],
    "NETWORKING": [
        "Ecris un serveur TCP Python async qui gere 100 connexions simultanees avec un protocol binaire custom (header 4 bytes length + payload). Code complet.",
        "Ecris un client HTTP Python avec retry, circuit breaker, connection pooling, et timeout adaptatif. Sans requests/httpx. Code complet.",
        "Ecris un serveur WebSocket Python minimaliste (sans lib) qui gere handshake, frames, ping/pong, et broadcast. Code complet.",
        "Ecris un DNS resolver Python simple qui interroge un serveur DNS et parse la reponse (A, AAAA, CNAME records). Code complet avec struct.pack/unpack.",
        "Ecris un port scanner Python async qui scanne 1000 ports en <5 secondes avec detection de service. Code complet avec asyncio.",
        "Ecris un reverse proxy Python qui load-balance entre 4 backends avec health check et sticky sessions. Code complet.",
        "Ecris un tunnel TCP Python (port forwarding local) qui forward le traffic d'un port local vers un host:port distant. Code complet.",
        "Ecris un service discovery Python pour LAN: broadcast UDP, registration, heartbeat, deregistration automatique. Code complet.",
        "Ecris un rate limiter HTTP middleware Python avec token bucket par IP et sliding window global. Code complet.",
        "Ecris un network monitor Python qui detecte les changements de latence et packet loss vers 4 hosts et genere des alertes. Code complet.",
    ],
    "AUTOMATION": [
        "Ecris un script Python qui cree et gere des scheduled tasks Windows via schtasks.exe: create, list, delete, enable/disable. Code complet.",
        "Ecris un module Python pour lire et ecrire dans le registre Windows: HKLM, HKCU, avec backup avant modification. Code complet avec winreg.",
        "Ecris un service manager Python pour Windows: lister, demarrer, arreter, restart les services. Status monitoring avec alertes. Code complet via subprocess.",
        "Ecris un script Python WMI qui collecte les infos systeme Windows: CPU, RAM, disques, GPU, processes, services. Code complet.",
        "Ecris un file organizer Python qui trie automatiquement les fichiers d'un dossier par extension, date, et taille avec regles configurables. Code complet.",
        "Ecris un clipboard manager Python pour Windows: historique des 50 derniers copier, recherche, restore. Code complet avec ctypes.",
        "Ecris un auto-updater Python pour une application: check version, download, verify hash, backup, replace, restart. Code complet.",
        "Ecris un log aggregator Python qui collecte les logs de 4 machines Windows (Event Log) et les centralise dans SQLite. Code complet.",
        "Ecris un script Python de monitoring de processus Windows: CPU%, RAM, restart automatique si crash, notification Telegram. Code complet.",
        "Ecris un backup scheduler Python pour Windows: incremental, compression zip, retention policy (7 daily, 4 weekly), restore. Code complet.",
    ],
    "AI_ML": [
        "Ecris un pipeline de fine-tuning QLoRA Python complet: load model, prepare dataset, configure LoRA, train, merge, save. Code avec transformers+peft.",
        "Ecris un module d'embeddings Python qui genere, stocke (SQLite), et recherche par similarite cosinus. Support batch. Code complet.",
        "Ecris un pipeline RAG Python minimaliste: chunk text, embed, store in vector DB (SQLite), retrieve top-k, generate. Code complet sans langchain.",
        "Propose 10 techniques de prompt engineering avancees pour la generation de code: self-consistency, tree-of-thought, meta-prompting. Exemples concrets.",
        "Ecris un evaluateur de LLM Python qui teste: accuracy, coherence, hallucination rate, instruction following. 5 metrics avec formules. Code complet.",
        "Ecris un optimiseur d'inference Python: quantization INT8, KV-cache optimization, batch scheduling. Benchmark avant/apres. Code complet.",
        "Ecris un systeme de prompt caching Python: hash du prompt, stockage reponse, invalidation par TTL et similarite semantique. Code complet.",
        "Ecris un model router Python qui choisit le meilleur modele (small/medium/large) selon la complexite du prompt. Classifier + routing rules. Code complet.",
        "Ecris un data augmentation pipeline Python pour un dataset de fine-tuning: paraphrase, back-translation, noise injection. Code complet.",
        "Ecris un systeme de guardrails Python pour LLM: detection de contenu toxique, PII, code dangereux, hallucination. 4 filtres avec scoring. Code complet.",
        "Ecris un inference server Python minimaliste avec batching dynamique, queue management, et timeout. Compatible avec l'API OpenAI. Code complet.",
        "Ecris un module Python de active learning qui selectionne les exemples les plus informatifs pour le fine-tuning. Uncertainty sampling + code complet.",
        "Propose un pipeline d'evaluation automatique de modeles IA: 5 benchmarks, scoring normalise, leaderboard SQLite. Architecture + code Python.",
        "Ecris un tokenizer BPE Python from scratch: train sur un corpus, encode, decode. 80 lignes max. Code complet.",
        "Ecris un systeme de model versioning Python: save/load checkpoints, metadata, compare performances entre versions. Code complet avec SQLite.",
    ],
    "DEVOPS_INFRA": [
        "Ecris un Dockerfile multi-stage pour une application Python avec LM Studio API: base CUDA, pip install, healthcheck, non-root user. Dockerfile complet.",
        "Ecris un pipeline CI/CD Python qui: lint (ruff), test (pytest), build, deploy. Script complet executable en local sans GitHub Actions.",
        "Ecris un monitoring stack Python: collecte metriques (CPU, RAM, GPU, latence), stockage SQLite, alertes Telegram, dashboard HTML. Code complet.",
        "Ecris un log aggregator Python avec rotation, compression, recherche full-text, et retention policy. Compatible multi-service. Code complet.",
        "Ecris un deploiement blue-green Python pour un service IA: 2 instances, health check, switch, rollback automatique. Code complet.",
        "Ecris un script Python de disaster recovery: backup DB + configs, restore, verification d'integrite, notification. Code complet.",
        "Ecris un service mesh Python simple pour un cluster de 4 noeuds: service discovery, load balancing, circuit breaker, retry. Code complet.",
        "Ecris un infrastructure-as-code Python qui configure un cluster IA: installe les deps, configure les ports, deploie les modeles. Script idempotent. Code complet.",
        "Ecris un canary deployment manager Python: deploy sur 1 noeud, monitor errors, rollout progressif ou rollback. Code complet.",
        "Ecris un chaos engineering tool Python pour tester la resilience d'un cluster IA: kill random node, inject latency, corrupt response. Code complet.",
    ],
}


def pick_tasks(n=8):
    """Pick n tasks, smartly routed to alive nodes by capability."""
    alive = get_alive_nodes()

    # Classify nodes by role (excluded nodes are skipped)
    fast = [nd for nd in alive if NODES[nd]["role"] == "fast"]      # M1
    deep = [nd for nd in alive if NODES[nd]["role"] == "deep"]      # M2, M3

    # Build weighted node pool: M1 gets most tasks (fast+reliable), no OL1
    pool = fast * 5 + deep * 2  # M1 x5, M2/M3 x2 each
    if not pool:
        pool = [n for n in alive if NODES[n]["role"] != "excluded"] or ["M1"]

    tasks = []
    cats = list(TASK_CATEGORIES.keys())
    for _ in range(n):
        cat = random.choice(cats)
        prompt = random.choice(TASK_CATEGORIES[cat])
        # Route: complex categories -> deep/fast preferred
        if cat in ("MATH", "CRYPTO_ANALYSIS", "AI_ML") and deep:
            node = random.choice(deep)
        elif cat in ("PYTHON_ADVANCED", "DATABASE", "NETWORKING", "DEVOPS_INFRA") and fast:
            node = random.choice(fast)
        elif cat == "AUTOMATION" and fast:
            node = random.choice(fast)
        else:
            node = random.choice(pool)
        tasks.append((node, cat, prompt))
    return tasks


# ── Database ─────────────────────────────────────────────────

def init_db():
    db = sqlite3.connect(str(DB_PATH), timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("""CREATE TABLE IF NOT EXISTS cluster_pipeline_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id TEXT,
        timestamp TEXT,
        node TEXT,
        category TEXT,
        prompt TEXT,
        response TEXT,
        elapsed_s REAL,
        error TEXT,
        tokens_est INTEGER,
        quality_score REAL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS cluster_pipeline_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id TEXT UNIQUE,
        timestamp TEXT,
        tasks_total INTEGER,
        tasks_ok INTEGER,
        nodes_used TEXT,
        avg_latency_s REAL,
        total_tokens_est INTEGER,
        duration_s REAL
    )""")
    db.commit()
    return db


def quality_score(response):
    """Estimate quality of response (0-1)."""
    if not response:
        return 0.0
    score = 0.0
    length = len(response)
    if length > 50:
        score += 0.2
    if length > 200:
        score += 0.2
    if "def " in response or "class " in response or "```" in response:
        score += 0.2  # Has code
    lines = response.strip().split("\n")
    if len(lines) >= 3:
        score += 0.2  # Structured
    if any(c in response for c in ["1.", "2.", "3.", "-", "*", "##"]):
        score += 0.2  # Formatted
    return min(score, 1.0)


# ── Cycle Execution ──────────────────────────────────────────

def run_cycle(db, cycle_num, tasks_per_cycle=8):
    """Execute one cycle of distributed tasks."""
    cycle_id = f"C{cycle_num}_{uuid.uuid4().hex[:6]}"
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cycle_start = time.time()

    tasks = pick_tasks(tasks_per_cycle)
    results = []

    # Run tasks sequentially (reliable for background/windowless mode)
    for i, (node, cat, prompt) in enumerate(tasks):
        try:
            resp, elapsed, err = query_node(node, prompt)
        except Exception as ex:
            resp, elapsed, err = None, 0, str(ex)[:120]
        qs = quality_score(resp) if resp else 0.0
        tokens = len((resp or "").split())
        results.append({
            "node": node, "cat": cat, "ok": resp is not None and err is None,
            "elapsed": elapsed, "tokens": tokens, "quality": qs
        })
        # Save to DB
        db.execute(
            "INSERT INTO cluster_pipeline_log (cycle_id, timestamp, node, category, prompt, response, elapsed_s, error, tokens_est, quality_score) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cycle_id, ts, node, cat, prompt[:300], (resp or "")[:4000],
             round(elapsed, 2), err, tokens, round(qs, 3)))

    # Cycle summary
    ok = sum(1 for r in results if r["ok"])
    nodes_used = list(set(r["node"] for r in results))
    avg_lat = sum(r["elapsed"] for r in results) / max(len(results), 1)
    total_tok = sum(r["tokens"] for r in results)
    duration = time.time() - cycle_start
    avg_q = sum(r["quality"] for r in results if r["ok"]) / max(ok, 1)

    db.execute(
        "INSERT INTO cluster_pipeline_cycles (cycle_id, timestamp, tasks_total, tasks_ok, nodes_used, avg_latency_s, total_tokens_est, duration_s) VALUES (?,?,?,?,?,?,?,?)",
        (cycle_id, ts, len(tasks), ok, json.dumps(nodes_used),
         round(avg_lat, 2), total_tok, round(duration, 2)))
    db.commit()

    # Print compact summary
    rate = ok * 100 // max(len(tasks), 1)
    print(f"  [{cycle_id}] {ok}/{len(tasks)} OK ({rate}%) | {duration:.0f}s | {total_tok}tok | Q={avg_q:.2f} | {','.join(nodes_used)}", flush=True)

    return {
        "cycle_id": cycle_id, "timestamp": ts,
        "tasks_total": len(tasks), "tasks_ok": ok,
        "nodes_used": nodes_used, "avg_latency_s": round(avg_lat, 2),
        "total_tokens": total_tok, "duration_s": round(duration, 2),
        "avg_quality": round(avg_q, 3)
    }


# ── Telegram Notifications ──────────────────────────────────

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}).encode()
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ── Status Report ────────────────────────────────────────────

def show_status():
    db = sqlite3.connect(str(DB_PATH))
    # Pipeline stats
    total = db.execute("SELECT COUNT(*) FROM cluster_pipeline_log").fetchone()[0]
    ok = db.execute("SELECT COUNT(*) FROM cluster_pipeline_log WHERE error IS NULL").fetchone()[0]
    cycles = db.execute("SELECT COUNT(*) FROM cluster_pipeline_cycles").fetchone()[0]

    print(f"\n=== CLUSTER PIPELINE STATUS ===")
    print(f"  Cycles: {cycles}")
    print(f"  Tasks: {total} total | {ok} OK ({ok * 100 // max(total, 1)}%)")

    # Per node
    rows = db.execute("""
        SELECT node, COUNT(*), SUM(CASE WHEN error IS NULL THEN 1 ELSE 0 END),
               AVG(elapsed_s), SUM(tokens_est), AVG(quality_score)
        FROM cluster_pipeline_log GROUP BY node
    """).fetchall()
    print(f"\n  Per node:")
    for node, cnt, ok_n, avg_lat, tok, avg_q in rows:
        print(f"    {node:10s}: {cnt:4d} tasks | {ok_n:4d} OK ({ok_n * 100 // max(cnt, 1):2d}%) | {avg_lat:.1f}s avg | {tok or 0} tok | Q={avg_q or 0:.2f}")

    # Per category
    rows = db.execute("""
        SELECT category, COUNT(*), SUM(CASE WHEN error IS NULL THEN 1 ELSE 0 END)
        FROM cluster_pipeline_log GROUP BY category ORDER BY COUNT(*) DESC
    """).fetchall()
    print(f"\n  Per category:")
    for cat, cnt, ok_c in rows:
        print(f"    {cat:15s}: {cnt:4d} ({ok_c:4d} OK)")

    # Last 5 cycles
    rows = db.execute("""
        SELECT cycle_id, timestamp, tasks_total, tasks_ok, duration_s, nodes_used
        FROM cluster_pipeline_cycles ORDER BY id DESC LIMIT 5
    """).fetchall()
    print(f"\n  Last 5 cycles:")
    for cid, ts, total_t, ok_t, dur, nodes in rows:
        print(f"    {ts} | {cid} | {ok_t}/{total_t} | {dur:.0f}s | {nodes}")

    # PID
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        print(f"\n  PID: {pid}")

    db.close()


# ── Main Loop ────────────────────────────────────────────────

def main():
    if "--status" in sys.argv:
        show_status()
        return

    max_cycles = 1000
    if "--cycles" in sys.argv:
        idx = sys.argv.index("--cycles")
        max_cycles = int(sys.argv[idx + 1])
        if max_cycles == 0:
            max_cycles = 999999

    tasks_per_cycle = 8
    if "--batch" in sys.argv:
        idx = sys.argv.index("--batch")
        tasks_per_cycle = int(sys.argv[idx + 1])

    pause = 5
    if "--pause" in sys.argv:
        idx = sys.argv.index("--pause")
        pause = int(sys.argv[idx + 1])

    # Kill existing pipeline instance if running
    if PID_FILE.exists():
        old_pid = PID_FILE.read_text().strip()
        try:
            subprocess.run(["taskkill", "/PID", old_pid, "/F"],
                           capture_output=True, timeout=5)
        except Exception:
            pass

    # Redirect stdout/stderr to log file for background mode
    log_file = TURBO / "data" / "pipeline_output.log"
    if "--log" in sys.argv or sys.stdout is None:
        fh = open(str(log_file), "w", encoding="utf-8", buffering=1)
        sys.stdout = fh
        sys.stderr = fh

    # Write PID
    PID_FILE.write_text(str(os.getpid()))

    print("=" * 60)
    print(f"  JARVIS AUTONOMOUS CLUSTER PIPELINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Cycles: {max_cycles} | Batch: {tasks_per_cycle} | Pause: {pause}s")
    print("=" * 60, flush=True)

    # Phase 1: Health check
    online = health_check_all()
    if not online:
        print("FATAL: No nodes online. Aborting.")
        sys.exit(1)

    # Phase 2: Init DB
    db = init_db()

    # Phase 3: Main loop
    total_ok, total_tasks = 0, 0
    health_interval = 50  # Re-check health every 50 cycles

    print(f"\n[PIPELINE] Starting {max_cycles} cycles...\n", flush=True)

    for cycle in range(1, max_cycles + 1):
        try:
            # Periodic health re-check
            if cycle % health_interval == 0:
                print(f"\n[HEALTH] Re-checking nodes (cycle {cycle})...")
                health_check_all()

            result = run_cycle(db, cycle, tasks_per_cycle)
            total_ok += result["tasks_ok"]
            total_tasks += result["tasks_total"]

            # Progress report every 25 cycles
            if cycle % 25 == 0:
                rate = total_ok * 100 // max(total_tasks, 1)
                print(f"\n  === PROGRESS: cycle {cycle}/{max_cycles} | {total_ok}/{total_tasks} OK ({rate}%) ===\n")

            # Telegram report every 100 cycles
            if cycle % 100 == 0:
                rate = total_ok * 100 // max(total_tasks, 1)
                send_telegram(
                    f"[PIPELINE] Cycle {cycle}/{max_cycles}\n"
                    f"Tasks: {total_ok}/{total_tasks} OK ({rate}%)\n"
                    f"Nodes: {','.join(get_alive_nodes())}"
                )

            time.sleep(pause)

        except KeyboardInterrupt:
            print(f"\n\n[STOP] Interrupted at cycle {cycle}")
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                print(f"\n[DB LOCKED] Cycle {cycle}: retrying in 15s...", flush=True)
                try:
                    db.close()
                except Exception:
                    pass
                time.sleep(15)
                db = init_db()
            else:
                print(f"\n[ERROR] Cycle {cycle}: {e}", flush=True)
                time.sleep(10)
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Cycle {cycle}: {e}", flush=True)
            traceback.print_exc()
            if hasattr(sys.stdout, 'flush'):
                sys.stdout.flush()
            time.sleep(10)

    # Phase 3: Final report
    rate = total_ok * 100 // max(total_tasks, 1)
    print(f"\n{'=' * 60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Cycles: {cycle} | Tasks: {total_ok}/{total_tasks} OK ({rate}%)")
    print(f"{'=' * 60}")

    send_telegram(
        f"[PIPELINE DONE] {cycle} cycles\n"
        f"Tasks: {total_ok}/{total_tasks} OK ({rate}%)"
    )

    db.close()
    PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log = TURBO / "data" / "pipeline_crash.log"
        with open(str(log), "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\nCRASH {datetime.now()}\n")
            traceback.print_exc(file=f)
        raise
