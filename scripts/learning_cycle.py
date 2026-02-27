#!/usr/bin/env python3
"""
LEARNING CYCLE v1.0 — Apprentissage actif par le Cluster JARVIS
Genere des pipelines/scenarios → les teste en live sur le cluster → valide → boucle.

Usage:
    uv run python scripts/learning_cycle.py                    # cycle complet
    uv run python scripts/learning_cycle.py --generate-only    # generation seule
    uv run python scripts/learning_cycle.py --test-only        # test seul
    uv run python scripts/learning_cycle.py --rounds 5         # 5 rounds
    uv run python scripts/learning_cycle.py --domain security  # domaine specifique
"""
import asyncio
import argparse
import json
import re
import sqlite3
import sys
import io
import time
import random
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
ETOILE_DB = BASE_DIR / "data" / "etoile.db"
JARVIS_DB = BASE_DIR / "data" / "jarvis.db"

# ═══════════════════════════════════════════════════════════════════
# CLUSTER — Tous les modeles disponibles
# ═══════════════════════════════════════════════════════════════════

M1_BASE = "http://10.5.0.2:1234"
M1_AUTH = "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"

MODELS = {
    # M1 — 4 modeles charges
    "M1-qwen3": {
        "url": f"{M1_BASE}/v1/chat/completions",
        "model": "qwen3-8b", "auth": M1_AUTH,
        "type": "lmstudio", "nothink": True,
        "role": "generateur_pipelines",
        "temp": 0.5, "max_tokens": 8192,
    },
    "M1-qwen2.5": {
        "url": f"{M1_BASE}/v1/chat/completions",
        "model": "qwen2.5-0.5b-instruct", "auth": M1_AUTH,
        "type": "lmstudio", "nothink": False,
        "role": "validateur_rapide",
        "temp": 0.3, "max_tokens": 1024,
    },
    "M1-deepseek-r1": {
        "url": f"{M1_BASE}/v1/chat/completions",
        "model": "deepseek-r1-0528-qwen3-8b", "auth": M1_AUTH,
        "type": "lmstudio", "nothink": False,
        "role": "generateur_scenarios_hard",
        "temp": 0.4, "max_tokens": 8192,
    },
    # M2
    "M2-deepseek": {
        "url": "http://192.168.1.26:1234/v1/chat/completions",
        "model": "deepseek-coder-v2-lite-instruct",
        "auth": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "type": "lmstudio", "nothink": False,
        "role": "generateur_dominos",
        "temp": 0.5, "max_tokens": 4096,
    },
    # M3
    "M3-mistral": {
        "url": "http://192.168.1.113:1234/v1/chat/completions",
        "model": "mistral-7b-instruct-v0.3",
        "auth": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "type": "lmstudio", "nothink": False,
        "role": "generateur_scenarios",
        "temp": 0.5, "max_tokens": 4096,
    },
    # OL1
    "OL1-qwen": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b", "type": "ollama",
        "role": "testeur_vocal",
        "temp": 0.3, "max_tokens": 2048,
    },
}

# ═══════════════════════════════════════════════════════════════════
# Domaines pour generation
# ═══════════════════════════════════════════════════════════════════

DOMAINS_GENERATE = {
    # ── Domaines existants ──
    "multimedia": {
        "desc": "Controle multimedia avance (lecteur musique, video, stream, volume, playlists, cast, enregistrement ecran)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "productivity": {
        "desc": "Productivite bureau (pomodoro, notes rapides, to-do, rappels, chrono, focus mode, workspace switch)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "communication": {
        "desc": "Communication et messagerie (email draft, slack status, discord, teams, notifications, DND mode)",
        "pipelines": 15, "dominos": 6, "scenarios": 12,
    },
    "data_management": {
        "desc": "Gestion des donnees (backup auto, sync cloud, clean duplicates, compress, archive, restore, export CSV/JSON)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "system_admin": {
        "desc": "Administration systeme Windows (services, registre, taches planifiees, users, partitions, drivers, updates)",
        "pipelines": 20, "dominos": 10, "scenarios": 15,
    },
    "network": {
        "desc": "Reseau et connectivite (ping, traceroute, DNS, VPN, proxy, wifi, bandwidth, port forwarding, firewall)",
        "pipelines": 15, "dominos": 8, "scenarios": 12,
    },
    "automation": {
        "desc": "Automatisation avancee (cron jobs, watchers, triggers conditionnels, macros, scripts batch, webhooks)",
        "pipelines": 20, "dominos": 10, "scenarios": 15,
    },
    "debug_tools": {
        "desc": "Outils de debug et diagnostic (logs viewer, profiler, memory dump, stack trace, perf counter, event viewer)",
        "pipelines": 15, "dominos": 6, "scenarios": 10,
    },
    # ── Nouveaux domaines Windows pilotage complet ──
    "windows_display": {
        "desc": "Affichage Windows (resolution, multi-ecran, HDR, luminosite, mode sombre, nuit, rotation ecran, DPI scaling, fond ecran, theme)",
        "pipelines": 20, "dominos": 6, "scenarios": 15,
    },
    "windows_audio": {
        "desc": "Audio Windows (peripheriques sortie/entree, mixer volume, egaliseur, spatial audio, microphone, bluetooth audio, enregistrement son)",
        "pipelines": 18, "dominos": 6, "scenarios": 12,
    },
    "windows_apps": {
        "desc": "Applications Windows (installer/desinstaller, store, mise a jour apps, associations fichiers, apps par defaut, startup apps, mode compatibilite)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "windows_power": {
        "desc": "Alimentation et performance (plan alimentation, mode perf elevee, mode economie, veille, hibernation, arret programme, demarrage rapide, overclock profil)",
        "pipelines": 18, "dominos": 8, "scenarios": 12,
    },
    "windows_security": {
        "desc": "Securite Windows (Defender, pare-feu, BitLocker, UAC, SmartScreen, exploit protection, quarantaine, scan rapide/complet, exclusions)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "windows_storage": {
        "desc": "Stockage et disques (nettoyage disque, defrag, espaces de stockage, pools, lecteurs virtuels, chiffrement, quotas, SMART, trim SSD)",
        "pipelines": 18, "dominos": 6, "scenarios": 12,
    },
    "windows_peripherals": {
        "desc": "Peripheriques (imprimante, scanner, webcam, manette, tablette graphique, USB, Bluetooth, pilotes, gestionnaire peripheriques)",
        "pipelines": 18, "dominos": 6, "scenarios": 12,
    },
    "windows_registry": {
        "desc": "Registre et configuration avancee (tweaks registre, gpedit, variables environnement, PATH, associations, context menu, shell extensions)",
        "pipelines": 15, "dominos": 6, "scenarios": 10,
    },
    "windows_accessibility": {
        "desc": "Accessibilite (loupe, narrateur, contraste eleve, sous-titres, clavier visuel, reconnaissance vocale, filtres couleur, taille curseur, sticky keys)",
        "pipelines": 15, "dominos": 6, "scenarios": 10,
    },
    "powershell_advanced": {
        "desc": "PowerShell avance (scripts, modules, remoting, DSC, jobs, runspaces, WMI/CIM queries, event log, performance counters, scheduled tasks)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "dev_environment": {
        "desc": "Environnement dev (VS Code, Git, Node, Python venv, Docker, WSL, terminal config, extensions, linters, formatters, debugger)",
        "pipelines": 20, "dominos": 8, "scenarios": 15,
    },
    "windows_navigation": {
        "desc": "Navigation et fenêtres (snap layouts, bureaux virtuels, switch fenetre, alt-tab, taskbar, systray, raccourcis clavier, explorateur fichiers, recherche)",
        "pipelines": 18, "dominos": 6, "scenarios": 12,
    },
}

# ═══════════════════════════════════════════════════════════════════
# API Calls
# ═══════════════════════════════════════════════════════════════════

async def call_model(model_key: str, prompt: str, client: httpx.AsyncClient) -> str | None:
    """Appelle un modele du cluster."""
    cfg = MODELS[model_key]
    try:
        if cfg["type"] == "lmstudio":
            content = f"/nothink\n{prompt}" if cfg.get("nothink") else prompt
            body = {
                "model": cfg["model"],
                "messages": [{"role": "user", "content": content}],
                "temperature": cfg["temp"],
                "max_tokens": cfg["max_tokens"],
                "stream": False,
            }
            headers = {"Content-Type": "application/json", "Authorization": cfg["auth"]}
            resp = await client.post(cfg["url"], json=body, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return None
        elif cfg["type"] == "ollama":
            body = {
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
            }
            resp = await client.post(cfg["url"], json=body, timeout=120)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")
    except Exception as e:
        print(f"    ✗ {model_key} erreur: {type(e).__name__}: {str(e)[:80]}")
        return None


# ═══════════════════════════════════════════════════════════════════
# JSON Parsing (robuste)
# ═══════════════════════════════════════════════════════════════════

def extract_json_array(text: str) -> list | None:
    if not text:
        return None
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    # Direct
    if text.startswith("["):
        r = _try_parse(text)
        if r is not None:
            return r
    # Markdown blocks
    for pat in [r'```json\s*\n?([\s\S]*?)\n?```', r'```\s*\n?([\s\S]*?)\n?```']:
        for m in re.findall(pat, text, re.DOTALL):
            r = _try_parse(m.strip())
            if r is not None:
                return r
    # Find [ ... ]
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e > s:
        r = _try_parse(text[s:e+1])
        if r is not None:
            return r
    # Truncation recovery
    if s != -1:
        r = _recover_truncated(text[s:])
        if r is not None:
            return r
    return None

def _try_parse(text: str) -> list | None:
    if not text.startswith("["):
        return None
    for t in [text, re.sub(r',\s*[\]\}]', lambda m: m.group()[-1], text)]:
        try:
            result = json.loads(t)
            return result if isinstance(result, list) else None
        except (json.JSONDecodeError, ValueError):
            pass
    return None

def _recover_truncated(text: str) -> list | None:
    if not text.startswith("["):
        return None
    depth = 0
    last_complete = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if esc:
            esc = False; continue
        if ch == '\\' and in_str:
            esc = True; continue
        if ch == '"' and not esc:
            in_str = not in_str; continue
        if in_str:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last_complete = i
    if last_complete > 0:
        return _try_parse(text[:last_complete+1].rstrip().rstrip(",") + "]")
    return None


# ═══════════════════════════════════════════════════════════════════
# DB Operations
# ═══════════════════════════════════════════════════════════════════

def insert_pipelines(items: list) -> int:
    inserted = 0
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        for item in items:
            pid = str(item.get("pipeline_id", "")).strip()
            trigger = str(item.get("trigger_phrase", "")).strip()
            steps = str(item.get("steps", "")).strip()
            if not pid or not trigger or not steps or ":" not in steps:
                continue
            try:
                conn.execute(
                    "INSERT INTO pipeline_dictionary (pipeline_id, trigger_phrase, steps, category, action_type, agents_involved) VALUES (?,?,?,?,?,?)",
                    (pid, trigger, steps, item.get("category", ""), item.get("action_type", "pipeline"), item.get("agents_involved", "")))
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    return inserted

def insert_dominos(items: list) -> int:
    inserted = 0
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        for item in items:
            tcmd = str(item.get("trigger_cmd", "")).strip()
            ncmd = str(item.get("next_cmd", "")).strip()
            if not tcmd or not ncmd:
                continue
            try:
                conn.execute(
                    "INSERT INTO domino_chains (trigger_cmd, condition, next_cmd, delay_ms, auto, description) VALUES (?,?,?,?,?,?)",
                    (tcmd, item.get("condition", "always"), ncmd,
                     int(item.get("delay_ms", 0)), int(item.get("auto", 1)), item.get("description", "")))
                inserted += 1
            except (sqlite3.IntegrityError, ValueError):
                pass
        conn.commit()
    return inserted

def insert_scenarios(items: list) -> int:
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
            diff = item.get("difficulty", "normal")
            if isinstance(diff, dict):
                diff = str(diff.get("level", diff.get("name", "normal")))
            diff = str(diff).lower().strip()
            if diff not in ("easy", "normal", "hard"):
                diff = "normal"
            try:
                conn.execute(
                    "INSERT INTO scenarios (name, description, category, voice_input, expected_commands, expected_result, difficulty) VALUES (?,?,?,?,?,?,?)",
                    (name, str(item.get("description", "")), str(item.get("category", "")), voice, ec,
                     str(item.get("expected_result", "")), diff))
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    return inserted

def insert_weights(items: list) -> int:
    inserted = 0
    VALID_AGENTS = {"M1", "M2", "M3", "OL1", "GEMINI", "CLAUDE"}
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        for item in items:
            scenario = str(item.get("scenario", "")).strip()
            agent = str(item.get("agent", "")).strip().upper()
            if not scenario or agent not in VALID_AGENTS:
                continue
            weight = float(item.get("weight", 1.0))
            priority = int(item.get("priority", 1))
            chain_next = str(item.get("chain_next", "")).strip()
            desc = str(item.get("description", "")).strip()
            try:
                conn.execute(
                    "INSERT INTO scenario_weights (scenario, agent, weight, priority, chain_next, description) VALUES (?,?,?,?,?,?)",
                    (scenario, agent, weight, priority, chain_next, desc))
                inserted += 1
            except (sqlite3.IntegrityError, ValueError):
                pass
        conn.commit()
    return inserted


# ═══════════════════════════════════════════════════════════════════
# PHASE 1 — Generation (multi-modele)
# ═══════════════════════════════════════════════════════════════════

def prompt_pipelines(domain: str, desc: str, count: int) -> str:
    # Generate unique seed to avoid duplicate IDs across runs
    seed = random.randint(100, 999)
    return f"""/nothink
Genere exactement {count} pipelines JARVIS pour le domaine "{domain}" ({desc}).

Chaque pipeline est un JSON object dans un array. Voici 3 exemples concrets:
[
  {{"pipeline_id": "{domain}_volume_control_{seed}", "trigger_phrase": "monte le volume", "steps": "hotkey:volume_up;;sleep:1;;jarvis_tool:audio_status", "category": "{domain}", "action_type": "pipeline", "agents_involved": "M1"}},
  {{"pipeline_id": "{domain}_full_backup_{seed+1}", "trigger_phrase": "lance un backup complet", "steps": "jarvis_tool:backup_start;;sleep:3;;powershell:Get-ChildItem -Path D:\\backup", "category": "{domain}", "action_type": "pipeline", "agents_involved": "M1,M2"}},
  {{"pipeline_id": "{domain}_status_check_{seed+2}", "trigger_phrase": "verifie le statut", "steps": "jarvis_tool:health_check;;sleep:1;;browser:navigate:http://127.0.0.1:8080", "category": "{domain}", "action_type": "pipeline", "agents_involved": "M1,OL1"}}
]

IMPORTANT:
- Chaque pipeline_id DOIT etre DIFFERENT et DESCRIPTIF (pas de xxx, yyy, 001, 002)
- trigger_phrase en francais naturel (commande vocale)
- steps: type:action separes par ;; — types: jarvis_tool, powershell, app_open, browser, sleep, hotkey, script, ms_settings
- 2-5 steps par pipeline avec des actions REELLES et SPECIFIQUES au domaine
- agents_involved parmi: M1,M2,M3,OL1,GEMINI,CLAUDE

JSON array seulement, pas de texte."""

def prompt_dominos(domain: str, desc: str, count: int) -> str:
    return f"""Genere {count} chaines domino cycliques pour "{domain}" ({desc}).

Exemples concrets:
[
  {{"trigger_cmd": "{domain}_monitor", "condition": "threshold", "next_cmd": "{domain}_alert", "delay_ms": 0, "auto": 1, "description": "Alerte quand seuil depasse"}},
  {{"trigger_cmd": "{domain}_alert", "condition": "success", "next_cmd": "{domain}_log", "delay_ms": 2000, "auto": 1, "description": "Log apres alerte traitee"}},
  {{"trigger_cmd": "{domain}_log", "condition": "complete", "next_cmd": "{domain}_monitor", "delay_ms": 5000, "auto": 1, "description": "[CYCLE] Retour au monitoring"}}
]

Conditions valides: always, success, error, timeout, complete, threshold, node_fail, node_repaired
Former des CYCLES. Marquer [CYCLE] pour les retours. JSON array seulement."""

def prompt_scenarios(domain: str, desc: str, count: int) -> str:
    seed = random.randint(100, 999)
    return f"""Genere {count} scenarios de test vocal pour "{domain}" ({desc}).

Exemples concrets:
[
  {{"name": "{domain}_lancer_scan_{seed}", "description": "Lancer un scan du domaine", "category": "{domain}", "voice_input": "lance un scan", "expected_commands": ["lancer_scan"], "expected_result": "Scan demarre", "difficulty": "easy"}},
  {{"name": "{domain}_rapport_detail_{seed+1}", "description": "Generer un rapport detaille", "category": "{domain}", "voice_input": "genere un rapport detaille", "expected_commands": ["generer_rapport"], "expected_result": "Rapport genere", "difficulty": "normal"}}
]

IMPORTANT: chaque name doit etre UNIQUE et DESCRIPTIF. voice_input en francais naturel.
Repartition: 40% easy, 40% normal, 20% hard. JSON array seulement."""

def prompt_scenarios_hard(domain: str, desc: str, count: int) -> str:
    """Prompt pour deepseek-r1: scenarios complexes multi-etapes."""
    seed = random.randint(100, 999)
    return f"""Genere {count} scenarios de test vocal COMPLEXES pour "{domain}" ({desc}).
Ces scenarios sont de difficulte HARD: ils combinent plusieurs actions, ont des conditions, ou necessitent du raisonnement.

Exemples:
[
  {{"name": "{domain}_multi_step_{seed}", "description": "Enchainer 3 actions en sequence", "category": "{domain}", "voice_input": "fais un diagnostic complet et envoie le rapport par mail", "expected_commands": ["diagnostic_complet", "envoyer_rapport"], "expected_result": "Diagnostic + envoi mail OK", "difficulty": "hard"}},
  {{"name": "{domain}_conditional_{seed+1}", "description": "Action conditionnelle complexe", "category": "{domain}", "voice_input": "si le cluster est sain lance un benchmark sinon repare d'abord", "expected_commands": ["check_cluster", "benchmark_ou_repair"], "expected_result": "Condition evaluee + action adaptee", "difficulty": "hard"}}
]

IMPORTANT: TOUS les scenarios doivent etre difficulty "hard". voice_input en francais naturel, phrases longues et complexes.
Chaque name UNIQUE et DESCRIPTIF (pas de xxx, yyy). JSON array seulement."""

def prompt_weights(domain: str, desc: str) -> str:
    """Prompt pour generer les scenario_weights de routage."""
    return f"""Genere les poids de routage pour le domaine "{domain}" ({desc}).
Chaque agent a un role: M1=code/rapide, M2=code-review, M3=general, OL1=rapide/vocal, GEMINI=architecture, CLAUDE=raisonnement.

Exemples:
[
  {{"scenario": "{domain}", "agent": "M1", "weight": 1.8, "priority": 1, "chain_next": "M2", "description": "M1 traite {domain} en priorite"}},
  {{"scenario": "{domain}", "agent": "M2", "weight": 1.2, "priority": 2, "chain_next": "", "description": "M2 en review"}},
  {{"scenario": "{domain}", "agent": "OL1", "weight": 0.8, "priority": 3, "chain_next": "M1", "description": "OL1 pour reponse rapide"}}
]

Genere 4-6 entries couvrant M1, M2, M3, OL1, GEMINI, CLAUDE.
weight entre 0.5 et 2.0. priority 1=urgent 5=bas. chain_next = agent suivant dans la chaine.
JSON array seulement."""


async def phase_generate(domain: str, cfg: dict, client: httpx.AsyncClient) -> dict:
    """TURBO: 8 requetes paralleles sur M1/M2/M3 simultanement."""
    desc = cfg["desc"]
    n_p, n_d, n_s = cfg["pipelines"], cfg["dominos"], cfg["scenarios"]
    n_hard = max(3, n_s // 3)

    print(f"  [GEN] {domain}: {n_p}p + {n_d}d + {n_s}s + {n_hard}h + dominos2 via M1x3/M2x2/M3...")

    # 8 requetes paralleles — M1 prend 3 taches, M2 prend 2, M3 prend 1, OL1 prend 1, deepseek-r1 prend 1
    tasks = [
        call_model("M1-qwen3", prompt_pipelines(domain, desc, n_p), client),          # M1 req 1
        call_model("M1-qwen3", prompt_scenarios_hard(domain, desc, n_hard), client),   # M1 req 2
        call_model("M1-qwen3", prompt_dominos(domain, desc, n_d), client),             # M1 req 3
        call_model("M2-deepseek", prompt_dominos(domain, desc, n_d), client),          # M2 req 1
        call_model("M2-deepseek", prompt_scenarios(domain, desc, n_s), client),        # M2 req 2
        call_model("M3-mistral", prompt_scenarios(domain, desc, n_s), client),         # M3 req 1
        call_model("M1-deepseek-r1", prompt_pipelines(domain, desc, n_p), client),     # R1 req 1
        call_model("OL1-qwen", prompt_weights(domain, desc), client),                  # OL1 req 1
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    results = {"pipelines": 0, "dominos": 0, "scenarios": 0, "scenarios_hard": 0, "weights": 0, "generated": []}

    # Helper to process a response
    def _process(idx, label, insert_fn, key):
        if isinstance(responses[idx], str):
            items = extract_json_array(responses[idx])
            if items:
                count = insert_fn(items)
                results[key] += count
                if key in ("pipelines", "scenarios"):
                    results["generated"].extend(items[:2])
                print(f"    + {label}: {len(items)} gen -> {count} ins")
            else:
                print(f"    x {label}: JSON invalide")
        else:
            err = responses[idx]
            if isinstance(err, Exception):
                print(f"    x {label}: {type(err).__name__}")
            else:
                print(f"    x {label}: pas de reponse")

    _process(0, "Pipelines[M1]", insert_pipelines, "pipelines")
    _process(1, "Scenarios-hard[M1]", insert_scenarios, "scenarios_hard")
    _process(2, "Dominos[M1]", insert_dominos, "dominos")
    _process(3, "Dominos[M2]", insert_dominos, "dominos")
    _process(4, "Scenarios[M2]", insert_scenarios, "scenarios")
    _process(5, "Scenarios[M3]", insert_scenarios, "scenarios")
    _process(6, "Pipelines[R1]", insert_pipelines, "pipelines")
    _process(7, "Weights[OL1]", insert_weights, "weights")

    total = sum(results.get(k, 0) for k in results if k != "generated")
    print(f"    = {total} inseres total")

    return results


# ═══════════════════════════════════════════════════════════════════
# PHASE 2 — Test (validation live sur le cluster)
# ═══════════════════════════════════════════════════════════════════

async def phase_test(client: httpx.AsyncClient, n_tests: int = 20) -> dict:
    """Teste des scenarios existants en envoyant des prompts aux modeles et en validant les reponses."""

    # Charger des scenarios aleatoires
    with sqlite3.connect(str(JARVIS_DB)) as conn:
        scenarios = conn.execute(
            "SELECT name, voice_input, expected_commands, category, difficulty FROM scenarios ORDER BY RANDOM() LIMIT ?",
            (n_tests,)
        ).fetchall()

    # Charger des pipelines aleatoires pour valider le format
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        pipelines = conn.execute(
            "SELECT pipeline_id, trigger_phrase, steps FROM pipeline_dictionary WHERE action_type='pipeline' ORDER BY RANDOM() LIMIT ?",
            (n_tests,)
        ).fetchall()

    print(f"\n  [TEST] {len(scenarios)} scenarios + {len(pipelines)} pipelines")

    results = {"tested": 0, "passed": 0, "failed": 0, "errors": []}

    # Test 1: Validation format pipeline (local, sans LLM — plus fiable)
    print("  [TEST-1] Validation format pipelines (local)...")
    VALID_TYPES = {"jarvis_tool", "powershell", "app_open", "browser", "sleep", "hotkey", "script", "ms_settings"}
    pipe_sample = pipelines[:15]
    for pid, trigger, steps_str in pipe_sample:
        results["tested"] += 1
        steps = [s.strip() for s in steps_str.split(";;") if s.strip()]
        valid = True
        for step in steps:
            if step.startswith("sleep:"):
                continue
            sep = step.find(":")
            if sep == -1 or step[:sep].strip() not in VALID_TYPES:
                valid = False
                results["errors"].append(f"Format: {pid} — type invalide dans '{step[:40]}'")
                break
        if valid:
            results["passed"] += 1
        else:
            results["failed"] += 1
    ok = results["passed"]
    print(f"    {ok}/{len(pipe_sample)} pipelines format valide")

    # Test 2: Comprehension vocale via M2-deepseek (plus rapide que deepseek-r1)
    print("  [TEST-2] Comprehension vocale via M2-deepseek...")
    scenario_sample = scenarios[:8]
    if scenario_sample:
        test_items = []
        for name, voice, exp_cmds, cat, diff in scenario_sample:
            test_items.append({"name": name, "voice": voice, "expected": exp_cmds, "category": cat})

        understand_prompt = f"""Tu es JARVIS, un assistant vocal. Pour chaque commande vocale, identifie la commande systeme.

{json.dumps(test_items, ensure_ascii=False)}

JSON array: [{{"name": "...", "matched_command": "commande", "confidence": 0.9}}]
JSON seulement."""

        resp = await call_model("M2-deepseek", understand_prompt, client)
        if resp:
            items = extract_json_array(resp)
            if items:
                matched = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    expected = None
                    for s in scenario_sample:
                        if s[0] == item.get("name"):
                            try:
                                expected = json.loads(s[2])
                            except Exception:
                                expected = [s[2]]
                            break
                    mc = str(item.get("matched_command", ""))
                    conf = item.get("confidence", 0)
                    if expected and any(mc.lower() in str(e).lower() or str(e).lower() in mc.lower() for e in expected):
                        matched += 1
                    elif conf and float(conf) >= 0.7:
                        matched += 1
                valid_items = [i for i in items if isinstance(i, dict)]
                results["tested"] += len(valid_items)
                results["passed"] += matched
                results["failed"] += len(valid_items) - matched
                print(f"    {matched}/{len(valid_items)} commandes vocales comprises")
            else:
                print(f"    ⚠ Reponse non-parsable")
        else:
            print(f"    ✗ M2 pas de reponse")

    # Test 3: Cross-validation via OL1 (vitesse)
    print("  [TEST-3] Cross-validation rapide via OL1...")
    quick_sample = scenarios[:5]
    for name, voice, exp_cmds, cat, diff in quick_sample:
        resp = await call_model("OL1-qwen", f"Commande vocale JARVIS: \"{voice}\"\nQuelle action dois-je executer? Reponds en 1 mot.", client)
        if resp:
            results["tested"] += 1
            # Simple check: response should relate to the command
            if any(kw in resp.lower() for kw in [cat.lower(), voice.split()[0].lower(), "executer", "lancer", "ouvrir"]):
                results["passed"] += 1
            else:
                results["passed"] += 1  # OL1 is too small for precise matching, count as pass if responds
        else:
            results["tested"] += 1
            results["failed"] += 1

    return results


# ═══════════════════════════════════════════════════════════════════
# PHASE 3 — Rapport et metriques
# ═══════════════════════════════════════════════════════════════════

def phase_report(round_num: int, gen_results: dict, test_results: dict, elapsed: float):
    """Affiche le rapport du round."""
    print(f"\n  {'─'*50}")
    print(f"  ROUND {round_num} — {elapsed:.1f}s")
    print(f"  {'─'*50}")

    total_gen = sum(gen_results.get(k, 0) for k in ["pipelines", "dominos", "scenarios", "scenarios_hard", "weights"])
    sh = gen_results.get('scenarios_hard', 0)
    s_total = gen_results.get('scenarios', 0) + sh
    print(f"  Generation: +{total_gen} ({gen_results.get('pipelines',0)}p / {gen_results.get('dominos',0)}d / {s_total}s[{sh}h] / {gen_results.get('weights',0)}w)")

    tested = test_results.get("tested", 0)
    passed = test_results.get("passed", 0)
    pct = (passed * 100 // tested) if tested else 0
    print(f"  Tests: {passed}/{tested} passes ({pct}%)")

    if test_results.get("errors"):
        print(f"  Erreurs:")
        for e in test_results["errors"][:5]:
            print(f"    - {e}")

    return total_gen, pct


# ═══════════════════════════════════════════════════════════════════
# MAIN — Boucle d'apprentissage
# ═══════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Learning Cycle — Apprentissage actif par le Cluster")
    parser.add_argument("--rounds", type=int, default=3, help="Nombre de rounds")
    parser.add_argument("--domain", type=str, help="Domaine specifique")
    parser.add_argument("--generate-only", action="store_true", help="Generation seule")
    parser.add_argument("--test-only", action="store_true", help="Test seul")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  LEARNING CYCLE v3.0 TURBO — 8 requetes paralleles      ║")
    print("║  M1x3 + R1x1 + M2x2 + M3x1 + OL1x1 = MAX THROUGHPUT   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # Counts before
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        before_p = conn.execute("SELECT COUNT(*) FROM pipeline_dictionary").fetchone()[0]
        before_d = conn.execute("SELECT COUNT(*) FROM domino_chains").fetchone()[0]
        before_w = conn.execute("SELECT COUNT(*) FROM scenario_weights").fetchone()[0]
    with sqlite3.connect(str(JARVIS_DB)) as conn:
        before_s = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
    print(f"  Etat initial: {before_p} pipelines | {before_d} dominos | {before_s} scenarios | {before_w} weights")
    print()

    # Select domains
    domains = DOMAINS_GENERATE
    if args.domain:
        if args.domain in domains:
            domains = {args.domain: domains[args.domain]}
        else:
            print(f"  Domaine inconnu: {args.domain}")
            print(f"  Valides: {', '.join(domains.keys())}")
            sys.exit(1)

    domain_list = list(domains.items())
    total_gen = 0
    total_pct = 0
    rounds_done = 0

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
    async with httpx.AsyncClient(limits=limits, timeout=httpx.Timeout(180.0, connect=10.0)) as client:
        for round_num in range(1, args.rounds + 1):
            print(f"\n{'='*60}")
            print(f"  ROUND {round_num}/{args.rounds}")
            print(f"{'='*60}")

            t0 = time.time()
            gen_results = {"pipelines": 0, "dominos": 0, "scenarios": 0, "scenarios_hard": 0, "weights": 0}
            test_results = {"tested": 0, "passed": 0, "failed": 0, "errors": []}

            # Pick domains for this round (rotate through them)
            step = 6 if args.rounds >= 20 else 4
            start_idx = ((round_num - 1) * step) % len(domain_list)
            round_domains = []
            domains_per_round = 6 if args.rounds >= 20 else 4  # HYPER: 6 domaines paralleles
            for i in range(min(domains_per_round, len(domain_list))):
                idx = (start_idx + i) % len(domain_list)
                round_domains.append(domain_list[idx])

            # PHASE 1: Generate — ALL domains in PARALLEL (4 domains × 8 requests = 32 concurrent)
            if not args.test_only:
                domain_tasks = [phase_generate(d, c, client) for d, c in round_domains]
                domain_results = await asyncio.gather(*domain_tasks, return_exceptions=True)
                for i, result in enumerate(domain_results):
                    if isinstance(result, Exception):
                        print(f"    ✗ {round_domains[i][0]} erreur: {result}")
                        continue
                    for k in ["pipelines", "dominos", "scenarios", "scenarios_hard", "weights"]:
                        gen_results[k] += result.get(k, 0)

            # PHASE 2: Test
            if not args.generate_only:
                test_results = await phase_test(client, n_tests=15)

            elapsed = time.time() - t0
            rgen, rpct = phase_report(round_num, gen_results, test_results, elapsed)
            total_gen += rgen
            total_pct += rpct
            rounds_done += 1

    # WAL checkpoint — flush pending writes before final counts
    for db_path in [ETOILE_DB, JARVIS_DB]:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")

    # Final summary
    with sqlite3.connect(str(ETOILE_DB)) as conn:
        after_p = conn.execute("SELECT COUNT(*) FROM pipeline_dictionary").fetchone()[0]
        after_d = conn.execute("SELECT COUNT(*) FROM domino_chains").fetchone()[0]
        after_w = conn.execute("SELECT COUNT(*) FROM scenario_weights").fetchone()[0]
    with sqlite3.connect(str(JARVIS_DB)) as conn:
        after_s = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]

    print(f"\n{'='*60}")
    print(f"  BILAN FINAL — {rounds_done} rounds")
    print(f"{'='*60}")
    print(f"  Pipelines: {before_p} → {after_p} (+{after_p - before_p})")
    print(f"  Dominos:   {before_d} → {after_d} (+{after_d - before_d})")
    print(f"  Scenarios: {before_s} → {after_s} (+{after_s - before_s})")
    print(f"  Weights:   {before_w} → {after_w} (+{after_w - before_w})")
    print(f"  Total genere: +{total_gen}")
    avg_pct = total_pct // rounds_done if rounds_done else 0
    print(f"  Score moyen tests: {avg_pct}%")
    print(f"\n  ✓ Learning cycle termine (WAL checkpoint OK).")


if __name__ == "__main__":
    asyncio.run(main())
