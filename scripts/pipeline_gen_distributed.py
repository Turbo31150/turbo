#!/usr/bin/env python3
"""
PIPELINE FACTORY DISTRIBUE v1.0 — Generation par le Cluster JARVIS
Utilise M1/M2/M3/OL1 pour generer massivement des pipelines, dominos, scenarios et weights.

Usage:
    uv run python scripts/pipeline_gen_distributed.py              # tous les domaines
    uv run python scripts/pipeline_gen_distributed.py --domain security  # un seul domaine
    uv run python scripts/pipeline_gen_distributed.py --dry-run    # test sans insertion
    uv run python scripts/pipeline_gen_distributed.py --check      # health check seulement
"""
import asyncio
import argparse
import json
import re
import sqlite3
import sys
import io
import time
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent.parent
ETOILE_DB = BASE_DIR / "data" / "etoile.db"
JARVIS_DB = BASE_DIR / "data" / "jarvis.db"

NODES = {
    "M1": {
        "url": "http://10.5.0.2:1234/v1/chat/completions",
        "health_url": "http://10.5.0.2:1234/api/v1/models",
        "model": "qwen3-8b",
        "auth": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "type": "lmstudio",
        "temp": 0.4,
        "max_tokens": 8192,
        "nothink": True,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "health_url": "http://192.168.1.26:1234/api/v1/models",
        "model": "deepseek-coder-v2-lite-instruct",
        "auth": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "type": "lmstudio",
        "temp": 0.5,
        "max_tokens": 4096,
        "nothink": False,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "health_url": "http://192.168.1.113:1234/api/v1/models",
        "model": "mistral-7b-instruct-v0.3",
        "auth": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "type": "lmstudio",
        "temp": 0.5,
        "max_tokens": 4096,
        "nothink": False,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "type": "ollama",
        "temp": 0.3,
        "max_tokens": 4096,
    },
}

# (domain, m1_pipelines, m2_dominos, m3_scenarios, ol1_weights)
DOMAINS = [
    ("cluster_ops",   30, 15, 20, 5),
    ("devops",        30, 10, 20, 4),
    ("trading_adv",   30, 15, 20, 5),
    ("ai_research",   25, 10, 15, 5),
    ("security",      20,  8, 15, 4),
    ("monitoring",    25, 10, 15, 5),
    ("emergency",     20, 15, 15, 5),
    ("routines",      25, 12, 20, 4),
    ("optimization",  20,  8, 10, 3),
    ("consensus",     15, 10, 15, 6),
]

DOMAIN_DESC = {
    "cluster_ops": "Gestion du cluster IA distribue (health check, failover, load balancing, model swap, node restart, VRAM monitoring, GPU thermal management)",
    "devops": "Operations DevOps (git workflow, deploy, CI/CD, tests automatises, linting, build, Docker, backup code, rollback, analyse logs)",
    "trading_adv": "Trading avance MEXC Futures 10x (analyse technique multi-timeframe, signaux IA, gestion risque, portfolio rebalancing, backtesting, alertes prix)",
    "ai_research": "Recherche IA (benchmarking modeles, fine-tuning QLoRA, evaluation qualite, dataset generation, embeddings, RAG, prompt engineering, A/B test)",
    "security": "Securite systeme Windows (audit permissions, scan ports, firewall rules, certificats SSL, antivirus check, backup securise, intrusion detection)",
    "monitoring": "Monitoring systeme et cluster (metriques CPU/RAM/GPU/VRAM, alertes seuils, dashboard update, logs rotation, disk space, network latency, uptime)",
    "emergency": "Procedures d'urgence (disaster recovery, failover automatique, rollback deploy, kill process zombie, emergency shutdown, data rescue, hotfix deploy)",
    "routines": "Routines automatisees quotidiennes (matin/soir/hebdo, nettoyage temp, maintenance DB, rapports periodiques, sync fichiers, archivage logs)",
    "optimization": "Optimisation performances (cache warmup, defragmentation, memory cleanup, process priority tuning, startup optimization, batch processing GPU)",
    "consensus": "Consensus multi-agent et orchestration (vote pondere, arbitrage disputes, quality scoring, cross-validation, ensemble decisions, confidence calibration)",
}

# ═══════════════════════════════════════════════════════════════════
# Prompts pour chaque noeud
# ═══════════════════════════════════════════════════════════════════

def prompt_pipelines(domain: str, count: int) -> str:
    """M1 genere les pipelines multi-step."""
    desc = DOMAIN_DESC[domain]
    return f"""/nothink
Genere exactement {count} pipelines JARVIS pour le domaine "{domain}" ({desc}).

Format: JSON array strict, chaque element:
{{"pipeline_id": "{domain}_xxx", "trigger_phrase": "phrase en francais", "steps": "type:action;;type:action", "category": "{domain}", "action_type": "pipeline", "agents_involved": "M1,M2"}}

Regles steps — chaque step = type:action separes par ;; :
- jarvis_tool:nom_outil (ex: jarvis_tool:cluster_check, jarvis_tool:gpu_status)
- powershell:commande (ex: powershell:Get-Process | Sort CPU -Desc | Select -First 5)
- app_open:app (ex: app_open:chrome, app_open:vscode)
- browser:navigate:url (ex: browser:navigate:https://grafana.local:3000)
- sleep:N (ex: sleep:2)
- hotkey:combo (ex: hotkey:ctrl+shift+t)

Contraintes:
- pipeline_id unique en snake_case, prefixe "{domain}_"
- trigger_phrase en francais naturel (commande vocale)
- 2 a 5 steps par pipeline, realistes et utiles
- agents_involved parmi: M1,M2,M3,OL1,GEMINI,CLAUDE
- Pas de doublons, chaque pipeline a un but distinct

Exemples pour inspiration:
- {{"pipeline_id": "cluster_health_full", "trigger_phrase": "diagnostic complet du cluster", "steps": "jarvis_tool:cluster_check;;sleep:2;;jarvis_tool:gpu_status;;sleep:1;;jarvis_tool:thermal_check", "category": "cluster_ops", "action_type": "pipeline", "agents_involved": "M1,M2,M3,OL1"}}
- {{"pipeline_id": "mode_trading", "trigger_phrase": "mode trading", "steps": "browser:navigate:https://www.tradingview.com;;browser:navigate:https://www.mexc.com;;browser:navigate:http://127.0.0.1:8080", "category": "trading", "action_type": "pipeline", "agents_involved": "OL1,M2"}}

Reponds UNIQUEMENT avec le JSON array valide. Pas de texte, pas de markdown, pas d'explication."""


def prompt_dominos(domain: str, count: int) -> str:
    """M2 genere les domino chains cycliques."""
    desc = DOMAIN_DESC[domain]
    return f"""Genere exactement {count} chaines domino pour le domaine "{domain}" ({desc}).

Format JSON array strict, chaque element:
{{"trigger_cmd": "commande_declencheur", "condition": "condition", "next_cmd": "commande_suivante", "delay_ms": 0, "auto": 1, "description": "description"}}

Regles:
- trigger_cmd: nom de commande (ex: {domain}_status, {domain}_check, {domain}_heal)
- condition: always | node_fail | timeout | success | complete | error | threshold | node_repaired
- next_cmd: commande executee ensuite
- delay_ms: delai en ms (0 a 30000)
- auto: 1=automatique, 0=confirmation manuelle
- FORMER DES CYCLES: A->B->C->A avec conditions d'arret (le retour utilise condition != always)
- Marquer [CYCLE] dans la description pour les retours au debut
- Chaque combinaison trigger_cmd+condition+next_cmd doit etre unique

Exemples:
- {{"trigger_cmd": "status", "condition": "node_fail", "next_cmd": "heal --status", "delay_ms": 0, "auto": 1, "description": "Auto-diagnostic quand noeud en panne"}}
- {{"trigger_cmd": "heal", "condition": "node_repaired", "next_cmd": "status", "delay_ms": 5000, "auto": 1, "description": "[CYCLE] Re-check status apres reparation"}}
- {{"trigger_cmd": "consensus", "condition": "complete", "next_cmd": "log_consensus", "delay_ms": 0, "auto": 1, "description": "Log consensus dans etoile.db"}}

Reponds UNIQUEMENT avec le JSON array valide. Pas de texte ni markdown."""


def prompt_scenarios(domain: str, count: int) -> str:
    """M3 genere les scenarios de validation vocale."""
    desc = DOMAIN_DESC[domain]
    return f"""Genere exactement {count} scenarios de test vocal pour "{domain}" ({desc}).

JSON array, chaque element:
{{"name": "{domain}_xxx", "description": "...", "category": "{domain}", "voice_input": "...", "expected_commands": ["cmd1", "cmd2"], "expected_result": "...", "difficulty": "easy"}}

Regles:
- name: snake_case unique, prefixe "{domain}_"
- voice_input: phrase francais naturel
- expected_commands: array de strings (1 a 3 commandes)
- difficulty: 40% easy, 40% normal, 20% hard
- Scenarios realistes et varies

Exemples:
- {{"name": "routine_check_cluster", "description": "Verifier etat du cluster", "category": "routine", "voice_input": "comment va le cluster", "expected_commands": ["statut_cluster"], "expected_result": "Status des machines", "difficulty": "normal"}}
- {{"name": "security_scan_ports", "description": "Scanner ports ouverts", "category": "security", "voice_input": "scanne les ports", "expected_commands": ["scan_ports"], "expected_result": "Liste des ports", "difficulty": "hard"}}

JSON array seulement, pas de texte."""


def prompt_weights(domain: str, count: int) -> str:
    """OL1 genere les scenario_weights de routage."""
    return f"""/no_think
Genere {count} scenario_weights pour le routage du domaine "{domain}" avec les agents M1,M2,M3,OL1,GEMINI,CLAUDE.

Format JSON array:
{{"scenario": "{domain}", "agent": "M1", "weight": 1.8, "priority": 1, "chain_next": "M2", "description": "Routing {domain} -> M1 (principal)"}}

Regles:
- scenario: toujours "{domain}"
- agent: un des 6 (M1,M2,M3,OL1,GEMINI,CLAUDE)
- weight: 0.5 a 2.0 — M1 generalement le plus haut (1.6-1.8)
- priority: 1=premier, 2=fallback, 3=dernier recours
- chain_next: agent suivant si echec (vide si terminal)
- Combo scenario+agent unique
- Ordonner par priority croissante

Reponds UNIQUEMENT avec le JSON array. Pas de texte."""


# ═══════════════════════════════════════════════════════════════════
# API Calls
# ═══════════════════════════════════════════════════════════════════

async def call_node(node_name: str, prompt: str, client: httpx.AsyncClient) -> str | None:
    """Appelle un noeud du cluster et retourne la reponse texte."""
    cfg = NODES[node_name]
    try:
        if cfg["type"] == "lmstudio":
            # OpenAI-compatible /v1/chat/completions
            content = f"/nothink\n{prompt}" if cfg.get("nothink") else prompt
            body = {
                "model": cfg["model"],
                "messages": [{"role": "user", "content": content}],
                "temperature": cfg["temp"],
                "max_tokens": cfg["max_tokens"],
                "stream": False,
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": cfg["auth"],
            }
            resp = await client.post(cfg["url"], json=body, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            # OpenAI format: choices[0].message.content
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return None

        elif cfg["type"] == "ollama":
            body = {
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }
            resp = await client.post(cfg["url"], json=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    except httpx.TimeoutException:
        print(f"  ✗ {node_name} TIMEOUT (120s)")
        return None
    except httpx.ConnectError:
        print(f"  ✗ {node_name} OFFLINE (connexion refusee)")
        return None
    except Exception as e:
        print(f"  ✗ {node_name} erreur: {type(e).__name__}: {e}")
        return None


async def health_check(client: httpx.AsyncClient) -> dict[str, bool]:
    """Verifie la disponibilite de chaque noeud."""
    status = {}
    for name, cfg in NODES.items():
        try:
            if cfg["type"] == "lmstudio":
                resp = await client.get(
                    cfg["health_url"],
                    headers={"Authorization": cfg["auth"]},
                    timeout=5,
                )
                resp.raise_for_status()
                models = resp.json().get("models", [])
                loaded = [m for m in models if m.get("loaded_instances")]
                status[name] = len(loaded) > 0
                if loaded:
                    print(f"  ✓ {name} OK — {len(loaded)} modele(s) charge(s)")
                else:
                    print(f"  ⚠ {name} UP mais aucun modele charge")
            elif cfg["type"] == "ollama":
                resp = await client.get(f"{cfg['url'].rsplit('/api/', 1)[0]}/api/tags", timeout=5)
                resp.raise_for_status()
                models = resp.json().get("models", [])
                status[name] = len(models) > 0
                print(f"  ✓ {name} OK — {len(models)} modele(s) disponibles")
        except Exception as e:
            status[name] = False
            print(f"  ✗ {name} OFFLINE — {type(e).__name__}")
    return status


# ═══════════════════════════════════════════════════════════════════
# JSON Extraction
# ═══════════════════════════════════════════════════════════════════

def extract_json_array(text: str) -> list | None:
    """Extrait un JSON array depuis une reponse LLM (gere markdown, texte parasite, trailing commas, truncation)."""
    if not text:
        return None

    text = text.strip()

    # Nettoyage: supprimer les balises <think>...</think> de qwen3
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # Essai direct
    if text.startswith("["):
        result = _try_parse_array(text)
        if result is not None:
            return result

    # Chercher dans les code blocks markdown
    for pattern in [r'```json\s*\n?([\s\S]*?)\n?```', r'```\s*\n?([\s\S]*?)\n?```']:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            result = _try_parse_array(match.strip())
            if result is not None:
                return result

    # Trouver [ ... ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        result = _try_parse_array(text[start:end + 1])
        if result is not None:
            return result

    # RECOVERY: JSON tronque — commence par [ mais pas de ] final
    # Chercher le dernier objet complet }
    if start != -1:
        candidate = text[start:]
        result = _recover_truncated_array(candidate)
        if result is not None:
            return result

    return None


def _recover_truncated_array(text: str) -> list | None:
    """Recupere un JSON array tronque en trouvant le dernier objet complet."""
    if not text.startswith("["):
        return None
    # Trouver le dernier } qui ferme un objet au top-level de l'array
    depth = 0
    last_complete = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last_complete = i
    if last_complete > 0:
        truncated = text[:last_complete + 1].rstrip().rstrip(",") + "]"
        result = _try_parse_array(truncated)
        if result:
            return result
    return None


def _try_parse_array(text: str) -> list | None:
    """Tente de parser un JSON array avec corrections automatiques."""
    if not text.startswith("["):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fix trailing commas
    fixed = re.sub(r',\s*\]', ']', text)
    fixed = re.sub(r',\s*\}', '}', fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # Fix single quotes
    try:
        fixed2 = fixed.replace("'", '"')
        return json.loads(fixed2)
    except (json.JSONDecodeError, Exception):
        pass
    return None


# ═══════════════════════════════════════════════════════════════════
# DB Operations
# ═══════════════════════════════════════════════════════════════════

def count_tables() -> dict[str, int]:
    """Compte les lignes dans les 4 tables cibles."""
    counts = {}
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        counts["pipeline_dictionary"] = conn.execute("SELECT COUNT(*) FROM pipeline_dictionary").fetchone()[0]
        counts["domino_chains"] = conn.execute("SELECT COUNT(*) FROM domino_chains").fetchone()[0]
        counts["scenario_weights"] = conn.execute("SELECT COUNT(*) FROM scenario_weights").fetchone()[0]
    with sqlite3.connect(str(JARVIS_DB)) as conn:
        counts["scenarios"] = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
    return counts


def insert_pipelines(items: list, dry_run: bool = False) -> int:
    """Insere les pipelines dans etoile.db, skip les doublons."""
    if dry_run:
        return len(items)
    inserted = 0
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        for item in items:
            pid = str(item.get("pipeline_id", "")).strip()
            trigger = str(item.get("trigger_phrase", "")).strip()
            steps = str(item.get("steps", "")).strip()
            if not pid or not trigger or not steps:
                continue
            try:
                conn.execute(
                    """INSERT INTO pipeline_dictionary
                       (pipeline_id, trigger_phrase, steps, category, action_type, agents_involved)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (pid, trigger, steps,
                     item.get("category", ""),
                     item.get("action_type", "pipeline"),
                     item.get("agents_involved", "")),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    return inserted


def insert_dominos(items: list, dry_run: bool = False) -> int:
    """Insere les domino chains dans etoile.db, skip les doublons."""
    if dry_run:
        return len(items)
    inserted = 0
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        for item in items:
            tcmd = str(item.get("trigger_cmd", "")).strip()
            ncmd = str(item.get("next_cmd", "")).strip()
            if not tcmd or not ncmd:
                continue
            try:
                conn.execute(
                    """INSERT INTO domino_chains
                       (trigger_cmd, condition, next_cmd, delay_ms, auto, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (tcmd,
                     item.get("condition", "always"),
                     ncmd,
                     int(item.get("delay_ms", 0)),
                     int(item.get("auto", 1)),
                     item.get("description", "")),
                )
                inserted += 1
            except (sqlite3.IntegrityError, ValueError):
                pass
        conn.commit()
    return inserted


def insert_scenarios(items: list, dry_run: bool = False) -> int:
    """Insere les scenarios dans jarvis.db, skip les doublons."""
    if dry_run:
        return len(items)
    inserted = 0
    with sqlite3.connect(str(JARVIS_DB)) as conn:
        for item in items:
            name = str(item.get("name", "")).strip()
            voice = str(item.get("voice_input", "")).strip()
            if not name or not voice:
                continue
            ec = item.get("expected_commands", "[]")
            if isinstance(ec, list):
                ec = json.dumps(ec)
            try:
                conn.execute(
                    """INSERT INTO scenarios
                       (name, description, category, voice_input, expected_commands, expected_result, difficulty)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (name,
                     item.get("description", ""),
                     item.get("category", ""),
                     voice, ec,
                     item.get("expected_result", ""),
                     item.get("difficulty", "normal")),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    return inserted


def insert_weights(items: list, dry_run: bool = False) -> int:
    """Insere les scenario_weights dans etoile.db, skip les doublons."""
    if dry_run:
        return len(items)
    inserted = 0
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        for item in items:
            scenario = str(item.get("scenario", "")).strip()
            agent = str(item.get("agent", "")).strip()
            if not scenario or not agent:
                continue
            try:
                conn.execute(
                    """INSERT INTO scenario_weights
                       (scenario, agent, weight, priority, chain_next, description)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (scenario, agent,
                     float(item.get("weight", 1.0)),
                     int(item.get("priority", 1)),
                     item.get("chain_next", ""),
                     item.get("description", "")),
                )
                inserted += 1
            except (sqlite3.IntegrityError, ValueError):
                pass
        conn.commit()
    return inserted


# ═══════════════════════════════════════════════════════════════════
# Domain Processing
# ═══════════════════════════════════════════════════════════════════

# Fallback mapping: if primary node is offline, use this one
FALLBACK = {
    "M1": "M2",
    "M2": "M3",
    "M3": "OL1",
    "OL1": "M1",
}

async def process_domain(
    domain: str,
    n_pipes: int, n_dominos: int, n_scenarios: int, n_weights: int,
    dry_run: bool = False,
    online_nodes: set[str] | None = None,
) -> dict[str, int]:
    """Traite un domaine: dispatch parallele aux 4 noeuds, collecte et insere."""
    print(f"\n{'='*60}")
    print(f"  DOMAINE: {domain.upper()}")
    print(f"  Cible: {n_pipes} pipelines | {n_dominos} dominos | {n_scenarios} scenarios | {n_weights} weights")
    print(f"{'='*60}")

    results = {"pipelines": 0, "dominos": 0, "scenarios": 0, "weights": 0}

    # Determine which nodes to use (with fallback)
    assignments = {
        "M1": ("pipelines", prompt_pipelines(domain, n_pipes), insert_pipelines, n_pipes),
        "M2": ("dominos", prompt_dominos(domain, n_dominos), insert_dominos, n_dominos),
        "M3": ("scenarios", prompt_scenarios(domain, n_scenarios), insert_scenarios, n_scenarios),
        "OL1": ("weights", prompt_weights(domain, n_weights), insert_weights, n_weights),
    }

    # Apply fallbacks for offline nodes
    final_assignments = {}
    for node, (key, prompt_text, inserter, count) in assignments.items():
        target = node
        if online_nodes and node not in online_nodes:
            fb = FALLBACK.get(node)
            if fb and (online_nodes is None or fb in online_nodes):
                print(f"  ⚠ {node} offline → fallback {fb} pour {key}")
                target = fb
            else:
                print(f"  ✗ {node} offline, pas de fallback → skip {key}")
                continue
        final_assignments[target] = final_assignments.get(target, [])
        final_assignments[target].append((key, prompt_text, inserter, count))

    async with httpx.AsyncClient() as client:
        print("  → Dispatch parallele...")
        t0 = time.time()

        # Build tasks — one per unique node
        tasks = []
        task_meta = []
        for node, items in final_assignments.items():
            for key, prompt_text, inserter, count in items:
                tasks.append(call_node(node, prompt_text, client))
                task_meta.append((node, key, inserter, count))

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - t0
        print(f"  ← Reponses recues en {elapsed:.1f}s")

        for (node, key, inserter, expected), resp in zip(task_meta, responses):
            if isinstance(resp, BaseException):
                print(f"  ✗ {node}/{key}: Exception — {resp}")
                continue
            if resp is None:
                print(f"  ✗ {node}/{key}: Pas de reponse")
                continue

            items = extract_json_array(resp)
            if items is None:
                preview = resp[:300].replace("\n", " ")
                print(f"  ✗ {node}/{key}: JSON invalide — {preview}")
                continue

            if not isinstance(items, list):
                print(f"  ✗ {node}/{key}: Reponse n'est pas un array")
                continue

            count = inserter(items, dry_run=dry_run)
            results[key] = count
            suffix = " (dry-run)" if dry_run else ""
            print(f"  ✓ {node}/{key}: {len(items)} generes → {count} inseres{suffix}")

    return results


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Pipeline Factory Distribue — Generation par le Cluster")
    parser.add_argument("--domain", type=str, help="Traiter un seul domaine")
    parser.add_argument("--dry-run", action="store_true", help="Test sans insertion DB")
    parser.add_argument("--check", action="store_true", help="Health check seulement")
    parser.add_argument("--no-check", action="store_true", help="Skip le health check initial")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  PIPELINE FACTORY DISTRIBUE v1.0                        ║")
    print("║  Generation par le Cluster — JARVIS Turbo v10.3         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    if not ETOILE_DB.exists():
        print(f"ERREUR: {ETOILE_DB} introuvable"); sys.exit(1)
    if not JARVIS_DB.exists():
        print(f"ERREUR: {JARVIS_DB} introuvable"); sys.exit(1)

    # Health check
    online_nodes = None
    if not args.no_check:
        print("─── Health Check Cluster ───")
        async with httpx.AsyncClient() as client:
            status = await health_check(client)
        online_nodes = {n for n, ok in status.items() if ok}
        print(f"\n  Noeuds en ligne: {', '.join(sorted(online_nodes)) or 'AUCUN'}")
        if not online_nodes:
            print("\n  ERREUR: Aucun noeud disponible. Arret.")
            sys.exit(1)
        print()

    if args.check:
        return

    # Count before
    before = count_tables()
    print("─── Etat AVANT generation ───")
    for table, count in before.items():
        print(f"  {table}: {count}")
    print()

    if args.dry_run:
        print("  ⚠ MODE DRY-RUN — aucune insertion DB\n")

    # Filter domains if --domain specified
    domains = DOMAINS
    if args.domain:
        domains = [(d, p, do, s, w) for d, p, do, s, w in DOMAINS if d == args.domain]
        if not domains:
            valid = [d for d, *_ in DOMAINS]
            print(f"ERREUR: Domaine '{args.domain}' inconnu. Valides: {', '.join(valid)}")
            sys.exit(1)

    # Process domains
    totals = {"pipelines": 0, "dominos": 0, "scenarios": 0, "weights": 0}
    domain_results = []

    for domain, n_p, n_d, n_s, n_w in domains:
        result = await process_domain(domain, n_p, n_d, n_s, n_w,
                                       dry_run=args.dry_run, online_nodes=online_nodes)
        domain_results.append((domain, result))
        for k in totals:
            totals[k] += result[k]

    # Count after
    after = count_tables()

    # Final report
    print(f"\n{'='*60}")
    print("  RAPPORT FINAL")
    print(f"{'='*60}")
    print()
    print("─── Resultats par domaine ───")
    print(f"  {'Domaine':<16} {'Pipes':>6} {'Dominos':>8} {'Scenarios':>10} {'Weights':>8}")
    print(f"  {'─'*50}")
    for domain, result in domain_results:
        print(f"  {domain:<16} {result['pipelines']:>6} {result['dominos']:>8} {result['scenarios']:>10} {result['weights']:>8}")
    print(f"  {'─'*50}")
    print(f"  {'TOTAL':<16} {totals['pipelines']:>6} {totals['dominos']:>8} {totals['scenarios']:>10} {totals['weights']:>8}")

    print()
    print("─── Comparaison AVANT / APRES ───")
    print(f"  {'Table':<25} {'Avant':>8} {'Apres':>8} {'Delta':>8}")
    print(f"  {'─'*50}")
    for table in before:
        delta = after[table] - before[table]
        sign = "+" if delta >= 0 else ""
        print(f"  {table:<25} {before[table]:>8} {after[table]:>8} {sign}{delta:>7}")
    total_b = sum(before.values())
    total_a = sum(after.values())
    delta_t = total_a - total_b
    print(f"  {'─'*50}")
    print(f"  {'TOTAL':<25} {total_b:>8} {total_a:>8} {'+'if delta_t>=0 else ''}{delta_t:>7}")
    print()

    # Validation domino cycles
    print("─── Validation Domino Cycles ───")
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        chains = conn.execute("SELECT trigger_cmd, condition, next_cmd FROM domino_chains").fetchall()
    cycle_count = sum(1 for _, _, desc in
                      conn.execute("SELECT trigger_cmd, condition, description FROM domino_chains").fetchall()
                      if desc and "[CYCLE]" in desc) if False else 0
    # Count cycles by checking if any next_cmd matches a trigger_cmd
    triggers = {c[0] for c in chains}
    nexts = {c[2] for c in chains}
    cyclic = triggers & nexts
    print(f"  Total chains: {len(chains)}")
    print(f"  Commandes cycliques (trigger & next): {len(cyclic)}")
    if cyclic:
        print(f"  Cycles detectes: {', '.join(sorted(cyclic)[:10])}{'...' if len(cyclic) > 10 else ''}")

    print()
    print("✓ Generation terminee." + (" (dry-run)" if args.dry_run else ""))


if __name__ == "__main__":
    asyncio.run(main())
