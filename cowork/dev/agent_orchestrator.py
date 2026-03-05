#!/usr/bin/env python3
"""
Agent Orchestrator — Orchestrateur d'agents IA autonomes sur cluster distribue.

Pipeline: tache -> decomposition -> dispatch agents -> collecte -> fusion -> livraison
Agents: Coder (gpt-oss:120b), Reviewer (devstral-2:123b), Tester (M1 qwen3-8b), Monitor (OL1 qwen3:1.7b)

Stdlib uniquement. Sortie JSON.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
import urllib.request
import urllib.error
import threading
import queue
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# --- Configuration du cluster ---

# Repertoire de base pour la base de donnees
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "orchestrator.db"

# Endpoints du cluster IA
CLUSTER_ENDPOINTS = {
    "M1": {
        "host": "127.0.0.1",
        "port": 1234,
        "type": "lmstudio",
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "health_url": "http://127.0.0.1:1234/api/v1/models",
        "description": "LM Studio - qwen3-8b (6 GPU 46GB)"
    },
    "OL1": {
        "host": "127.0.0.1",
        "port": 11434,
        "type": "ollama",
        "url": "http://127.0.0.1:11434/api/chat",
        "health_url": "http://127.0.0.1:11434/api/tags",
        "description": "Ollama - qwen3:1.7b + cloud models"
    },
    "M2": {
        "host": "192.168.1.26",
        "port": 1234,
        "type": "lmstudio",
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "health_url": "http://192.168.1.26:1234/api/v1/models",
        "description": "LM Studio - deepseek-coder-v2 (3 GPU 24GB)"
    },
    "M3": {
        "host": "192.168.1.113",
        "port": 1234,
        "type": "lmstudio",
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "health_url": "http://192.168.1.113:1234/api/v1/models",
        "description": "LM Studio - mistral-7b (1 GPU 8GB)"
    }
}

# Definition des agents integres avec leur role, modele et noeud
BUILT_IN_AGENTS = {
    "Coder": {
        "role": "Generateur de code principal",
        "model": "gpt-oss:120b-cloud",
        "node": "OL1",
        "priority": 1,
        "weight": 1.9,
        "capabilities": ["code_generation", "refactoring", "architecture"],
        "ollama_model": "gpt-oss:120b-cloud"
    },
    "Reviewer": {
        "role": "Revue de code et audit qualite",
        "model": "devstral-2:123b-cloud",
        "node": "OL1",
        "priority": 2,
        "weight": 1.5,
        "capabilities": ["code_review", "security_audit", "best_practices"],
        "ollama_model": "devstral-2:123b-cloud"
    },
    "Tester": {
        "role": "Generation et validation de tests",
        "model": "qwen3-8b",
        "node": "M1",
        "priority": 3,
        "weight": 1.8,
        "capabilities": ["test_generation", "validation", "edge_cases"],
        "lmstudio_model": "qwen3-8b"
    },
    "Monitor": {
        "role": "Surveillance et health checks rapides",
        "model": "qwen3:1.7b",
        "node": "OL1",
        "priority": 4,
        "weight": 1.3,
        "capabilities": ["monitoring", "quick_check", "status_report"],
        "ollama_model": "qwen3:1.7b"
    }
}

# Niveaux de priorite pour la file d'attente
PRIORITY_LEVELS = {"critical": 0, "high": 1, "normal": 2, "low": 3}

# Nombre max de tentatives en cas d'echec
MAX_RETRIES = 3
# Timeout par defaut pour les appels HTTP (secondes)
HTTP_TIMEOUT = 120


# --- Base de donnees ---

def init_db():
    """Initialise la base SQLite avec les tables necessaires."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    # Table des taches deployees
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'normal',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            subtasks_count INTEGER DEFAULT 0,
            subtasks_done INTEGER DEFAULT 0
        )
    """)

    # Table des sous-taches distribuees aux agents
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subtasks (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 2,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            response TEXT,
            error TEXT,
            retries INTEGER DEFAULT 0,
            duration_ms REAL,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)

    # Table de sante des agents
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_health (
            agent_name TEXT NOT NULL,
            node TEXT NOT NULL,
            status TEXT DEFAULT 'unknown',
            last_check TEXT,
            latency_ms REAL,
            models_loaded INTEGER DEFAULT 0,
            error TEXT,
            PRIMARY KEY (agent_name, node)
        )
    """)

    # Table de configuration (scaling, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT
        )
    """)

    # Table des logs d'orchestration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT DEFAULT 'INFO',
            source TEXT,
            message TEXT,
            details TEXT
        )
    """)

    conn.commit()

    # Valeur par defaut pour le scaling
    cursor.execute(
        "INSERT OR IGNORE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
        ("max_concurrent", "3", _now())
    )
    conn.commit()
    conn.close()


def get_db():
    """Retourne une connexion SQLite configuree."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now():
    """Retourne le timestamp ISO 8601 UTC courant."""
    return datetime.now(timezone.utc).isoformat()


def _log(level, source, message, details=None):
    """Enregistre une entree dans la table logs."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO logs (timestamp, level, source, message, details) VALUES (?, ?, ?, ?, ?)",
            (_now(), level, source, message, json.dumps(details) if details else None)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Le logging ne doit jamais bloquer le pipeline


# --- Communication avec les noeuds du cluster ---

def _http_post(url, payload, timeout=HTTP_TIMEOUT):
    """Envoie une requete POST JSON et retourne la reponse parsee."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.URLError as e:
        raise ConnectionError(f"Erreur connexion {url}: {e}")
    except Exception as e:
        raise RuntimeError(f"Erreur HTTP {url}: {e}")


def _http_get(url, timeout=5):
    """Envoie une requete GET et retourne la reponse parsee."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except Exception as e:
        raise ConnectionError(f"GET {url} echoue: {e}")


def query_ollama(model, prompt, timeout=HTTP_TIMEOUT):
    """Envoie une requete a Ollama et retourne le contenu de la reponse."""
    url = CLUSTER_ENDPOINTS["OL1"]["url"]
    # think:false obligatoire pour les modeles cloud
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False
    }
    resp = _http_post(url, payload, timeout=timeout)
    # Extraction: .message.content
    return resp.get("message", {}).get("content", "")


def query_lmstudio(node, model, prompt, timeout=HTTP_TIMEOUT):
    """Envoie une requete a LM Studio (Responses API) et retourne le contenu."""
    endpoint = CLUSTER_ENDPOINTS[node]
    url = endpoint["url"]
    # /nothink obligatoire pour eviter le thinking cache de Qwen3
    payload = {
        "model": model,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": 4096,
        "stream": False,
        "store": False
    }
    resp = _http_post(url, payload, timeout=timeout)
    # Extraction: dernier element type=message dans .output[]
    output_list = resp.get("output", [])
    for item in reversed(output_list):
        if item.get("type") == "message":
            content_parts = item.get("content", [])
            texts = [p.get("text", "") for p in content_parts if p.get("type") == "output_text"]
            return "\n".join(texts)
    # Fallback: premier element avec content
    if output_list:
        first = output_list[0]
        if isinstance(first, dict) and "content" in first:
            content = first["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(resp)


def query_agent(agent_name, prompt, timeout=HTTP_TIMEOUT):
    """Interroge un agent specifique en utilisant le bon endpoint et modele."""
    agent_cfg = BUILT_IN_AGENTS[agent_name]
    node = agent_cfg["node"]
    endpoint_type = CLUSTER_ENDPOINTS[node]["type"]

    if endpoint_type == "ollama":
        model = agent_cfg.get("ollama_model", agent_cfg["model"])
        return query_ollama(model, prompt, timeout=timeout)
    elif endpoint_type == "lmstudio":
        model = agent_cfg.get("lmstudio_model", agent_cfg["model"])
        return query_lmstudio(node, model, prompt, timeout=timeout)
    else:
        raise ValueError(f"Type endpoint inconnu pour {node}: {endpoint_type}")


# --- Health check des agents ---

def check_agent_health(agent_name):
    """Verifie la sante d'un agent et met a jour la base."""
    agent_cfg = BUILT_IN_AGENTS[agent_name]
    node = agent_cfg["node"]
    endpoint = CLUSTER_ENDPOINTS[node]
    health_url = endpoint["health_url"]

    result = {
        "agent": agent_name,
        "node": node,
        "model": agent_cfg["model"],
        "status": "offline",
        "latency_ms": None,
        "models_loaded": 0,
        "error": None,
        "checked_at": _now()
    }

    start = time.time()
    try:
        data = _http_get(health_url, timeout=5)
        latency = (time.time() - start) * 1000

        if endpoint["type"] == "lmstudio":
            # Compter les modeles charges (avec loaded_instances)
            models = data.get("data", data.get("models", []))
            loaded = len([m for m in models if m.get("loaded_instances")])
            result["models_loaded"] = loaded
            result["status"] = "online" if loaded > 0 else "idle"
        elif endpoint["type"] == "ollama":
            models = data.get("models", [])
            result["models_loaded"] = len(models)
            result["status"] = "online" if models else "idle"

        result["latency_ms"] = round(latency, 1)
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "offline"

    # Enregistrement en base
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO agent_health (agent_name, node, status, last_check, latency_ms, models_loaded, error)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (agent_name, node, result["status"], result["checked_at"],
          result["latency_ms"], result["models_loaded"], result["error"]))
    conn.commit()
    conn.close()

    _log("INFO", "health_check", f"Agent {agent_name} sur {node}: {result['status']}", result)
    return result


def check_all_agents():
    """Verifie la sante de tous les agents en parallele."""
    results = {}
    threads = []
    lock = threading.Lock()

    def _check(name):
        r = check_agent_health(name)
        with lock:
            results[name] = r

    for agent_name in BUILT_IN_AGENTS:
        t = threading.Thread(target=_check, args=(agent_name,), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10)

    return results


# --- Decomposition de tache ---

def decompose_task(description):
    """
    Decompose une tache en sous-taches pour chaque agent.
    Chaque agent recoit un prompt adapte a son role.
    """
    subtasks = []

    # Coder: generer le code demande
    subtasks.append({
        "agent": "Coder",
        "prompt": (
            f"Tu es un expert en programmation. Genere le code pour la tache suivante.\n"
            f"Tache: {description}\n\n"
            f"Retourne uniquement le code avec des commentaires explicatifs."
        ),
        "priority": BUILT_IN_AGENTS["Coder"]["priority"]
    })

    # Reviewer: analyser la tache pour des problemes potentiels
    subtasks.append({
        "agent": "Reviewer",
        "prompt": (
            f"Tu es un reviewer de code expert. Analyse la tache suivante et identifie:\n"
            f"1. Les risques potentiels\n"
            f"2. Les bonnes pratiques a respecter\n"
            f"3. Les cas limites a couvrir\n\n"
            f"Tache: {description}"
        ),
        "priority": BUILT_IN_AGENTS["Reviewer"]["priority"]
    })

    # Tester: generer des tests
    subtasks.append({
        "agent": "Tester",
        "prompt": (
            f"Tu es un expert en tests logiciels. Pour la tache suivante, propose:\n"
            f"1. Les tests unitaires necessaires\n"
            f"2. Les cas limites a tester\n"
            f"3. Les scenarios d'integration\n\n"
            f"Tache: {description}"
        ),
        "priority": BUILT_IN_AGENTS["Tester"]["priority"]
    })

    # Monitor: evaluer la faisabilite et les ressources
    subtasks.append({
        "agent": "Monitor",
        "prompt": (
            f"Evalue rapidement la tache suivante:\n"
            f"1. Complexite estimee (simple/moyen/complexe)\n"
            f"2. Temps estime\n"
            f"3. Ressources necessaires\n\n"
            f"Tache: {description}"
        ),
        "priority": BUILT_IN_AGENTS["Monitor"]["priority"]
    })

    return subtasks


# --- File de priorite et execution ---

class PriorityTaskQueue:
    """File d'attente avec priorite pour les sous-taches."""

    def __init__(self):
        self._queue = queue.PriorityQueue()
        self._counter = 0  # Pour ordonner les taches de meme priorite

    def push(self, priority, subtask_data):
        """Ajoute une sous-tache avec sa priorite (0 = plus haute)."""
        self._counter += 1
        self._queue.put((priority, self._counter, subtask_data))

    def pop(self):
        """Retire et retourne la sous-tache la plus prioritaire."""
        if self._queue.empty():
            return None
        _, _, data = self._queue.get()
        return data

    def empty(self):
        return self._queue.empty()

    def size(self):
        return self._queue.qsize()


def execute_subtask(subtask_id, agent_name, prompt, retries=MAX_RETRIES):
    """
    Execute une sous-tache avec retry automatique.
    Retourne le resultat ou l'erreur.
    """
    conn = get_db()
    conn.execute(
        "UPDATE subtasks SET status = 'running', started_at = ? WHERE id = ?",
        (_now(), subtask_id)
    )
    conn.commit()
    conn.close()

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            _log("INFO", "executor", f"Execution {agent_name} (tentative {attempt}/{retries})",
                 {"subtask_id": subtask_id})

            start_time = time.time()
            response = query_agent(agent_name, prompt)
            duration_ms = (time.time() - start_time) * 1000

            # Succes: mise a jour en base
            conn = get_db()
            conn.execute("""
                UPDATE subtasks SET status = 'completed', completed_at = ?,
                response = ?, duration_ms = ?, retries = ?
                WHERE id = ?
            """, (_now(), response, round(duration_ms, 1), attempt - 1, subtask_id))
            conn.commit()
            conn.close()

            _log("INFO", "executor", f"{agent_name} termine en {duration_ms:.0f}ms",
                 {"subtask_id": subtask_id, "duration_ms": duration_ms})

            return {
                "subtask_id": subtask_id,
                "agent": agent_name,
                "status": "completed",
                "response": response,
                "duration_ms": round(duration_ms, 1),
                "retries": attempt - 1
            }

        except Exception as e:
            last_error = str(e)
            _log("WARNING", "executor",
                 f"{agent_name} echec tentative {attempt}: {last_error}",
                 {"subtask_id": subtask_id})
            if attempt < retries:
                time.sleep(2 * attempt)  # Backoff exponentiel simplifie

    # Toutes les tentatives echouees
    conn = get_db()
    conn.execute("""
        UPDATE subtasks SET status = 'failed', completed_at = ?,
        error = ?, retries = ?
        WHERE id = ?
    """, (_now(), last_error, retries, subtask_id))
    conn.commit()
    conn.close()

    return {
        "subtask_id": subtask_id,
        "agent": agent_name,
        "status": "failed",
        "error": last_error,
        "retries": retries
    }


# --- Pipeline principal ---

def deploy_task(description, priority="normal"):
    """
    Pipeline complet: tache -> decomposition -> dispatch -> collecte -> fusion -> livraison.
    """
    task_id = str(uuid.uuid4())[:12]
    now = _now()

    # Enregistrer la tache
    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (id, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, description, "decomposing", priority, now, now)
    )
    conn.commit()
    conn.close()

    _log("INFO", "pipeline", f"Nouvelle tache {task_id}: {description[:80]}",
         {"task_id": task_id, "priority": priority})

    # Etape 1: Decomposition
    subtask_defs = decompose_task(description)

    # Recuperer le scaling courant
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key = 'max_concurrent'").fetchone()
    max_concurrent = int(row["value"]) if row else 3
    conn.close()

    # Enregistrer les sous-taches
    subtask_records = []
    pq = PriorityTaskQueue()

    conn = get_db()
    for st_def in subtask_defs:
        st_id = str(uuid.uuid4())[:12]
        conn.execute("""
            INSERT INTO subtasks (id, task_id, agent_name, prompt, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (st_id, task_id, st_def["agent"], st_def["prompt"], st_def["priority"], now))
        pq.push(st_def["priority"], {
            "id": st_id,
            "agent": st_def["agent"],
            "prompt": st_def["prompt"]
        })
        subtask_records.append(st_id)

    conn.execute(
        "UPDATE tasks SET status = 'dispatching', subtasks_count = ?, updated_at = ? WHERE id = ?",
        (len(subtask_defs), _now(), task_id)
    )
    conn.commit()
    conn.close()

    # Etape 2: Dispatch parallele avec limitation de concurrence
    results = []
    results_lock = threading.Lock()
    semaphore = threading.Semaphore(max_concurrent)

    def _worker(st_data):
        semaphore.acquire()
        try:
            r = execute_subtask(st_data["id"], st_data["agent"], st_data["prompt"])
            with results_lock:
                results.append(r)
                # Mettre a jour le compteur
                done = len(results)
                try:
                    c = get_db()
                    c.execute(
                        "UPDATE tasks SET subtasks_done = ?, updated_at = ? WHERE id = ?",
                        (done, _now(), task_id)
                    )
                    c.commit()
                    c.close()
                except Exception:
                    pass
        finally:
            semaphore.release()

    threads = []
    while not pq.empty():
        st_data = pq.pop()
        t = threading.Thread(target=_worker, args=(st_data,), daemon=True)
        threads.append(t)
        t.start()

    # Attendre toutes les sous-taches (timeout global 5 min)
    for t in threads:
        t.join(timeout=300)

    # Etape 3: Fusion des resultats
    merged = {
        "task_id": task_id,
        "description": description,
        "priority": priority,
        "agents_results": {},
        "summary": {
            "total": len(subtask_defs),
            "completed": 0,
            "failed": 0,
            "total_duration_ms": 0
        }
    }

    for r in results:
        agent_name = r["agent"]
        merged["agents_results"][agent_name] = {
            "status": r["status"],
            "response": r.get("response", r.get("error", "")),
            "duration_ms": r.get("duration_ms", 0),
            "retries": r.get("retries", 0)
        }
        if r["status"] == "completed":
            merged["summary"]["completed"] += 1
            merged["summary"]["total_duration_ms"] += r.get("duration_ms", 0)
        else:
            merged["summary"]["failed"] += 1

    # Statut final de la tache
    final_status = "completed" if merged["summary"]["failed"] == 0 else "partial"
    if merged["summary"]["completed"] == 0:
        final_status = "failed"

    merged["summary"]["status"] = final_status
    merged["summary"]["total_duration_ms"] = round(merged["summary"]["total_duration_ms"], 1)

    # Enregistrer le resultat
    conn = get_db()
    conn.execute("""
        UPDATE tasks SET status = ?, completed_at = ?, updated_at = ?, result = ?
        WHERE id = ?
    """, (final_status, _now(), _now(), json.dumps(merged, ensure_ascii=False), task_id))
    conn.commit()
    conn.close()

    _log("INFO", "pipeline", f"Tache {task_id} terminee: {final_status}", merged["summary"])
    return merged


# --- Commandes CLI ---

def cmd_deploy(args):
    """Deploie une nouvelle tache sur le cluster."""
    description = " ".join(args.deploy)
    priority = getattr(args, "priority", "normal") or "normal"
    result = deploy_task(description, priority=priority)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_status(args):
    """Affiche le statut de toutes les taches."""
    conn = get_db()
    tasks = conn.execute("""
        SELECT id, description, status, priority, created_at, completed_at,
               subtasks_count, subtasks_done
        FROM tasks ORDER BY created_at DESC LIMIT 20
    """).fetchall()
    conn.close()

    output = {
        "timestamp": _now(),
        "tasks_count": len(tasks),
        "tasks": []
    }

    for t in tasks:
        output["tasks"].append({
            "id": t["id"],
            "description": t["description"][:100],
            "status": t["status"],
            "priority": t["priority"],
            "progress": f"{t['subtasks_done']}/{t['subtasks_count']}",
            "created_at": t["created_at"],
            "completed_at": t["completed_at"]
        })

    print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_scale(args):
    """Modifie le nombre d'agents concurrents (1-5)."""
    n = args.scale
    if n < 1 or n > 5:
        result = {"error": "Le scaling doit etre entre 1 et 5", "value": n}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
        ("max_concurrent", str(n), _now())
    )
    conn.commit()
    conn.close()

    _log("INFO", "scaling", f"Scaling modifie a {n} agents concurrents")
    result = {
        "action": "scale",
        "max_concurrent": n,
        "updated_at": _now(),
        "message": f"Scaling ajuste a {n} agent(s) concurrent(s)"
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_logs(args):
    """Affiche les logs recents de l'orchestrateur."""
    conn = get_db()
    limit = getattr(args, "limit", 50) or 50
    logs = conn.execute("""
        SELECT id, timestamp, level, source, message, details
        FROM logs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    output = {
        "timestamp": _now(),
        "logs_count": len(logs),
        "logs": []
    }

    for log in logs:
        entry = {
            "id": log["id"],
            "timestamp": log["timestamp"],
            "level": log["level"],
            "source": log["source"],
            "message": log["message"]
        }
        if log["details"]:
            try:
                entry["details"] = json.loads(log["details"])
            except (json.JSONDecodeError, TypeError):
                entry["details"] = log["details"]
        output["logs"].append(entry)

    print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_agents(args):
    """Affiche la liste des agents et leur sante."""
    # Verifier la sante de tous les agents
    health_results = check_all_agents()

    # Recuperer le scaling
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key = 'max_concurrent'").fetchone()
    max_concurrent = int(row["value"]) if row else 3
    conn.close()

    output = {
        "timestamp": _now(),
        "max_concurrent": max_concurrent,
        "agents_count": len(BUILT_IN_AGENTS),
        "agents": {}
    }

    for name, cfg in BUILT_IN_AGENTS.items():
        health = health_results.get(name, {})
        output["agents"][name] = {
            "role": cfg["role"],
            "model": cfg["model"],
            "node": cfg["node"],
            "weight": cfg["weight"],
            "capabilities": cfg["capabilities"],
            "endpoint": CLUSTER_ENDPOINTS[cfg["node"]]["url"],
            "health": {
                "status": health.get("status", "unknown"),
                "latency_ms": health.get("latency_ms"),
                "models_loaded": health.get("models_loaded", 0),
                "error": health.get("error")
            }
        }

    # Resume des noeuds du cluster
    output["cluster_nodes"] = {}
    for node_name, node_cfg in CLUSTER_ENDPOINTS.items():
        output["cluster_nodes"][node_name] = {
            "host": node_cfg["host"],
            "port": node_cfg["port"],
            "type": node_cfg["type"],
            "description": node_cfg["description"]
        }

    print(json.dumps(output, indent=2, ensure_ascii=False))


# --- Point d'entree ---

def main():
    """Point d'entree principal avec parsing des arguments CLI."""
    parser = argparse.ArgumentParser(
        description="Agent Orchestrator — Orchestrateur d'agents IA autonomes sur cluster distribue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python agent_orchestrator.py --deploy "Creer un serveur REST FastAPI"
  python agent_orchestrator.py --deploy "Optimiser la DB" --priority high
  python agent_orchestrator.py --status
  python agent_orchestrator.py --scale 4
  python agent_orchestrator.py --logs
  python agent_orchestrator.py --logs --limit 10
  python agent_orchestrator.py --agents

Agents integres:
  Coder    gpt-oss:120b  (OL1 cloud)   — Generation de code
  Reviewer devstral-2     (OL1 cloud)   — Revue de code
  Tester   qwen3-8b       (M1 local)    — Tests
  Monitor  qwen3:1.7b     (OL1 local)   — Surveillance
        """
    )

    # Arguments mutuellement exclusifs pour les commandes principales
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deploy", nargs="+", metavar="TASK",
                       help="Deployer une tache sur le cluster d'agents")
    group.add_argument("--status", action="store_true",
                       help="Afficher le statut de toutes les taches")
    group.add_argument("--scale", type=int, metavar="N",
                       help="Ajuster le nombre d'agents concurrents (1-5)")
    group.add_argument("--logs", action="store_true",
                       help="Afficher les logs recents de l'orchestrateur")
    group.add_argument("--agents", action="store_true",
                       help="Lister les agents et leur etat de sante")

    # Options additionnelles
    parser.add_argument("--priority", choices=["critical", "high", "normal", "low"],
                        default="normal",
                        help="Priorite de la tache (defaut: normal)")
    parser.add_argument("--limit", type=int, default=50,
                        help="Nombre de logs a afficher (defaut: 50)")

    args = parser.parse_args()

    # Initialiser la base de donnees
    init_db()

    # Router vers la commande appropriee
    if args.deploy:
        cmd_deploy(args)
    elif args.status:
        cmd_status(args)
    elif args.scale is not None:
        cmd_scale(args)
    elif args.logs:
        cmd_logs(args)
    elif args.agents:
        cmd_agents(args)


if __name__ == "__main__":
    main()
