#!/usr/bin/env python3
"""JARVIS Mega Improvement Loop — Boucle autonome d'amélioration continue.

Analyse les gaps, crée des commandes/skills, teste et log chaque cycle.
Conçu pour tourner en daemon via systemd ou nohup.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR = Path("/home/turbo/jarvis")
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jarvis.db"
SKILLS_FILE = DATA_DIR / "skills.json"
HISTORY_FILE = DATA_DIR / "action_history.json"
CYCLES_LOG = DATA_DIR / "improve_cycles.jsonl"
PID_FILE = Path("/tmp/jarvis-mega-improve.pid")

# ── Cluster IA endpoints (jamais localhost) ──────────────────────────────────
M1_HOST = os.getenv("M1_HOST", "127.0.0.1")
M1_PORT = os.getenv("M1_PORT", "1234")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("mega-improve")

# ── Flag d'arrêt propre ──────────────────────────────────────────────────────
_running = True


def _signal_handler(signum, frame):
    global _running
    log.info("Signal %s reçu — arrêt propre après le cycle en cours", signum)
    _running = False


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ═══════════════════════════════════════════════════════════════════════════════
# Utilitaires DB
# ═══════════════════════════════════════════════════════════════════════════════

def _db_connect() -> sqlite3.Connection | None:
    """Connexion sqlite3 avec row_factory."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as exc:
        log.error("Impossible d'ouvrir jarvis.db : %s", exc)
        return None


def _db_query(query: str, params: tuple = ()) -> list[dict]:
    """Exécute une requête SELECT et retourne une liste de dicts."""
    conn = _db_connect()
    if not conn:
        return []
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.error("Erreur SQL (%s) : %s", query[:60], exc)
        return []
    finally:
        conn.close()


def _db_execute(query: str, params: tuple = ()) -> bool:
    """Exécute une requête INSERT/UPDATE."""
    conn = _db_connect()
    if not conn:
        return False
    try:
        conn.execute(query, params)
        conn.commit()
        return True
    except Exception as exc:
        log.error("Erreur SQL write (%s) : %s", query[:60], exc)
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 : Analyse
# ═══════════════════════════════════════════════════════════════════════════════

def load_action_history(limit: int = 200) -> list[dict]:
    """Charge l'historique d'actions depuis le fichier JSON."""
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[-limit:]
    except Exception as exc:
        log.warning("Lecture action_history.json échouée : %s", exc)
    return []


def load_voice_analytics_failures(limit: int = 100) -> list[dict]:
    """Récupère les commandes vocales échouées depuis voice_analytics."""
    return _db_query(
        "SELECT text, stage, method, confidence, timestamp "
        "FROM voice_analytics WHERE success = 0 "
        "ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )


def load_existing_triggers() -> set[str]:
    """Collecte tous les triggers existants (voice_commands + skills.json)."""
    triggers = set()

    # Depuis voice_commands (DB)
    rows = _db_query("SELECT triggers FROM voice_commands WHERE enabled = 1")
    for row in rows:
        try:
            tlist = json.loads(row["triggers"])
            if isinstance(tlist, list):
                for t in tlist:
                    triggers.add(t.strip().lower())
            else:
                triggers.add(str(row["triggers"]).strip().lower())
        except (json.JSONDecodeError, TypeError):
            triggers.add(str(row["triggers"]).strip().lower())

    # Depuis skills.json
    try:
        if SKILLS_FILE.exists():
            skills = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
            for s in skills:
                for t in s.get("triggers", []):
                    triggers.add(t.strip().lower())
    except Exception:
        pass

    return triggers


def load_low_success_commands(threshold: float = 0.5) -> list[dict]:
    """Commandes existantes avec un taux de succès faible."""
    return _db_query(
        "SELECT name, triggers, action_type, action, success_count, fail_count "
        "FROM voice_commands "
        "WHERE enabled = 1 AND (success_count + fail_count) > 2 "
        "AND CAST(success_count AS REAL) / MAX(success_count + fail_count, 1) < ? "
        "ORDER BY fail_count DESC LIMIT 20",
        (threshold,),
    )


def identify_gaps() -> list[dict]:
    """Identifie les gaps : commandes demandées mais non reconnues."""
    failures = load_voice_analytics_failures(200)
    existing = load_existing_triggers()
    gaps = []
    seen_texts = set()

    for f in failures:
        text = (f.get("text") or "").strip().lower()
        if not text or len(text) < 3 or text in seen_texts:
            continue
        seen_texts.add(text)

        # Vérifier si ce texte matche un trigger existant
        matched = False
        for trigger in existing:
            if text == trigger or text in trigger or trigger in text:
                matched = True
                break
        if not matched:
            gaps.append({
                "text": text,
                "stage": f.get("stage", ""),
                "confidence": f.get("confidence", 0),
                "count": 1,
            })

    # Agréger les doublons proches
    aggregated = {}
    for g in gaps:
        key = g["text"][:30]
        if key in aggregated:
            aggregated[key]["count"] += 1
        else:
            aggregated[key] = g
    return list(aggregated.values())


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 : Création automatique
# ═══════════════════════════════════════════════════════════════════════════════

def query_cluster_ai(prompt: str, timeout: int = 15) -> str | None:
    """Interroge le cluster IA (LM Studio M1 ou Ollama) pour générer du contenu."""
    # Essai LM Studio M1
    endpoints = [
        f"http://{M1_HOST}:{M1_PORT}/v1/chat/completions",
        f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate",
    ]

    # Tentative LM Studio (format OpenAI)
    try:
        payload = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(
            endpoints[0],
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception:
        pass

    # Fallback Ollama
    try:
        payload = json.dumps({
            "model": "llama3",
            "prompt": prompt,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            endpoints[1],
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except Exception as exc:
        log.debug("Cluster IA indisponible : %s", exc)
        return None


def generate_command_for_gap(gap: dict) -> dict | None:
    """Génère une commande vocale pour combler un gap via le cluster IA."""
    text = gap["text"]

    # Prompt pour le cluster IA
    prompt = (
        f"Tu es JARVIS, un assistant vocal Linux. "
        f"L'utilisateur a dit : \"{text}\" mais aucune commande n'a été reconnue. "
        f"Génère une commande bash Linux adaptée. "
        f"Réponds UNIQUEMENT au format JSON strict : "
        f'{{ "name": "nom_commande", "action_type": "bash", "action": "commande_bash", '
        f'"description": "description courte", "triggers": ["trigger1", "trigger2"] }}'
    )

    ai_response = query_cluster_ai(prompt)
    if not ai_response:
        # Fallback : générer une commande basique localement
        return _generate_local_command(text)

    # Parser la réponse IA
    try:
        # Extraire le JSON de la réponse
        match = re.search(r'\{[^{}]+\}', ai_response)
        if match:
            cmd = json.loads(match.group())
            # Validation minimale
            if all(k in cmd for k in ("name", "action_type", "action", "triggers")):
                cmd.setdefault("description", f"Commande auto-générée pour '{text}'")
                cmd.setdefault("category", "auto_generated")
                return cmd
    except (json.JSONDecodeError, KeyError):
        pass

    return _generate_local_command(text)


def _generate_local_command(text: str) -> dict | None:
    """Fallback local : génère une commande basique sans IA."""
    # Mapping de patterns courants
    patterns = {
        r"(ouvre|lance|démarre|demarre)\s+(\w+)": lambda m: {
            "name": f"ouvre_{m.group(2)}",
            "action_type": "bash",
            "action": m.group(2),
            "description": f"Ouvre {m.group(2)}",
            "triggers": [text],
            "category": "auto_generated",
        },
        r"(ferme|arrête|arrete|kill)\s+(\w+)": lambda m: {
            "name": f"ferme_{m.group(2)}",
            "action_type": "bash",
            "action": f"pkill -f {m.group(2)}",
            "description": f"Ferme {m.group(2)}",
            "triggers": [text],
            "category": "auto_generated",
        },
        r"(volume|son)\s+(\d+)": lambda m: {
            "name": f"volume_{m.group(2)}",
            "action_type": "bash",
            "action": f"pactl set-sink-volume @DEFAULT_SINK@ {m.group(2)}%",
            "description": f"Volume à {m.group(2)}%",
            "triggers": [text],
            "category": "auto_generated",
        },
        r"(statut|status|état|etat)\s+(.*)" : lambda m: {
            "name": f"statut_{m.group(2).replace(' ', '_')}",
            "action_type": "bash",
            "action": f"systemctl --user status jarvis-{m.group(2).replace(' ', '-')} 2>/dev/null || echo 'Service non trouvé'",
            "description": f"Statut de {m.group(2)}",
            "triggers": [text],
            "category": "auto_generated",
        },
    }

    for pattern, builder in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return builder(m)

    return None


def insert_voice_command(cmd: dict) -> bool:
    """Insère une nouvelle commande vocale dans la DB."""
    triggers_json = json.dumps(cmd.get("triggers", []), ensure_ascii=False)
    params_json = json.dumps(cmd.get("params", []), ensure_ascii=False)
    return _db_execute(
        "INSERT OR IGNORE INTO voice_commands "
        "(name, category, description, triggers, action_type, action, params, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            cmd["name"],
            cmd.get("category", "auto_generated"),
            cmd.get("description", ""),
            triggers_json,
            cmd.get("action_type", "bash"),
            cmd.get("action", ""),
            params_json,
            time.time(),
        ),
    )


def create_skill_from_gaps(gaps: list[dict]) -> int:
    """Crée un skill si un pattern se répète (3+ gaps dans la même catégorie)."""
    # Grouper les gaps par premier mot
    groups: dict[str, list[dict]] = {}
    for g in gaps:
        first_word = g["text"].split()[0] if g["text"].split() else "misc"
        groups.setdefault(first_word, []).append(g)

    skills_created = 0
    for keyword, group_gaps in groups.items():
        if len(group_gaps) < 3:
            continue

        skill_name = f"auto_{keyword}_{int(time.time()) % 10000}"
        triggers = [g["text"] for g in group_gaps[:5]]
        steps = []
        for g in group_gaps[:5]:
            cmd = generate_command_for_gap(g)
            if cmd:
                steps.append({
                    "tool": cmd.get("action_type", "bash"),
                    "args": {"command": cmd.get("action", "")},
                    "description": cmd.get("description", g["text"]),
                    "wait_for_result": True,
                })

        if not steps:
            continue

        skill = {
            "name": skill_name,
            "description": f"Skill auto-généré pour le pattern '{keyword}'",
            "triggers": triggers,
            "steps": steps,
            "category": "auto_generated",
            "created_at": time.time(),
            "usage_count": 0,
            "last_used": 0.0,
            "success_rate": 1.0,
            "confirm": False,
        }

        if _add_skill_to_json(skill):
            skills_created += 1
            log.info("  Skill créé : %s (%d étapes)", skill_name, len(steps))

    return skills_created


def _add_skill_to_json(skill: dict) -> bool:
    """Ajoute un skill au fichier skills.json."""
    try:
        skills = []
        if SKILLS_FILE.exists():
            skills = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
            if not isinstance(skills, list):
                skills = []

        # Vérifier doublon
        existing_names = {s.get("name") for s in skills}
        if skill["name"] in existing_names:
            return False

        skills.append(skill)
        SKILLS_FILE.write_text(
            json.dumps(skills, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        log.error("Erreur écriture skills.json : %s", exc)
        return False


def add_alternative_triggers(low_success: list[dict]) -> int:
    """Ajoute des triggers alternatifs pour les commandes à faible taux de succès."""
    added = 0
    for cmd in low_success:
        name = cmd.get("name", "")
        try:
            triggers = json.loads(cmd.get("triggers", "[]"))
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(triggers, list) or not triggers:
            continue

        # Générer des variantes phonétiques/synonymes
        new_triggers = _generate_trigger_variants(triggers[0], name)
        all_triggers = list(set(triggers + new_triggers))

        if len(all_triggers) > len(triggers):
            triggers_json = json.dumps(all_triggers, ensure_ascii=False)
            if _db_execute(
                "UPDATE voice_commands SET triggers = ? WHERE name = ?",
                (triggers_json, name),
            ):
                added += len(all_triggers) - len(triggers)
                log.info("  +%d triggers pour '%s'", len(all_triggers) - len(triggers), name)

    return added


def _generate_trigger_variants(trigger: str, name: str) -> list[str]:
    """Génère des variantes d'un trigger vocal."""
    variants = []
    words = trigger.lower().split()

    # Synonymes courants
    synonyms = {
        "ouvre": ["lance", "démarre", "affiche"],
        "ferme": ["arrête", "stop", "kill", "quitte"],
        "montre": ["affiche", "donne"],
        "statut": ["status", "état", "etat"],
        "lance": ["ouvre", "démarre", "exécute"],
        "cherche": ["recherche", "trouve"],
    }

    if words and words[0] in synonyms:
        for syn in synonyms[words[0]]:
            variant = " ".join([syn] + words[1:])
            variants.append(variant)

    # Variante avec/sans article
    if len(words) >= 2 and words[1] in ("le", "la", "les", "l'", "un", "une", "du", "des"):
        variants.append(" ".join([words[0]] + words[2:]))
    elif len(words) >= 2:
        variants.append(" ".join([words[0], "le"] + words[1:]))

    return variants[:3]  # Maximum 3 variantes


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 : Test
# ═══════════════════════════════════════════════════════════════════════════════

def verify_command_syntax(cmd: dict) -> bool:
    """Vérifie qu'une commande a une syntaxe valide."""
    try:
        if not cmd.get("name") or not cmd.get("action"):
            return False
        if not isinstance(cmd.get("triggers"), list) or len(cmd["triggers"]) == 0:
            return False
        # Vérifier que l'action n'est pas dangereuse
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd", ":(){ :|:& };:"]
        action = cmd.get("action", "")
        for d in dangerous:
            if d in action:
                log.warning("  Commande dangereuse bloquée : %s", action)
                return False
        return True
    except Exception:
        return False


def verify_skills_loadable() -> bool:
    """Vérifie que skills.json est chargeable et valide."""
    try:
        if not SKILLS_FILE.exists():
            return True
        data = json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            log.error("skills.json n'est pas une liste")
            return False
        for i, skill in enumerate(data):
            if not skill.get("name"):
                log.error("Skill #%d sans nom", i)
                return False
            if not isinstance(skill.get("triggers", []), list):
                log.error("Skill '%s' : triggers invalides", skill["name"])
                return False
            if not isinstance(skill.get("steps", []), list):
                log.error("Skill '%s' : steps invalides", skill["name"])
                return False
        log.info("  skills.json valide (%d skills)", len(data))
        return True
    except json.JSONDecodeError as exc:
        log.error("skills.json corrompu : %s", exc)
        return False
    except Exception as exc:
        log.error("Erreur vérification skills.json : %s", exc)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 : Log
# ═══════════════════════════════════════════════════════════════════════════════

def log_cycle(cycle_data: dict):
    """Log un cycle dans improve_cycles.jsonl."""
    try:
        CYCLES_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CYCLES_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(cycle_data, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.error("Erreur écriture cycles log : %s", exc)


# ═══════════════════════════════════════════════════════════════════════════════
# Boucle principale
# ═══════════════════════════════════════════════════════════════════════════════

def run_cycle(cycle_num: int) -> dict:
    """Exécute un cycle complet d'amélioration."""
    t0 = time.time()
    result = {
        "cycle": cycle_num,
        "timestamp": datetime.now().isoformat(),
        "gaps_found": 0,
        "skills_created": 0,
        "commands_added": 0,
        "triggers_added": 0,
        "duration_s": 0,
        "errors": [],
    }

    log.info("═══ Cycle %d ═══════════════════════════════════════════", cycle_num)

    # ── Phase 1 : Analyse ──
    log.info("[Phase 1] Analyse des gaps...")
    try:
        history = load_action_history()
        log.info("  %d entrées dans action_history.json", len(history))

        failures = load_voice_analytics_failures()
        log.info("  %d échecs dans voice_analytics", len(failures))

        gaps = identify_gaps()
        result["gaps_found"] = len(gaps)
        log.info("  %d gaps identifiés", len(gaps))

        low_success = load_low_success_commands()
        log.info("  %d commandes à faible taux de succès", len(low_success))
    except Exception as exc:
        log.error("Erreur Phase 1 : %s", exc)
        result["errors"].append(f"Phase 1: {exc}")
        gaps = []
        low_success = []

    # ── Phase 2 : Création automatique ──
    log.info("[Phase 2] Création auto...")
    commands_added = 0
    try:
        for gap in gaps[:10]:  # Limiter à 10 par cycle pour ne pas surcharger
            cmd = generate_command_for_gap(gap)
            if cmd and verify_command_syntax(cmd):
                if insert_voice_command(cmd):
                    commands_added += 1
                    log.info("  + Commande ajoutée : %s → %s", cmd["name"], cmd.get("action", "")[:50])
        result["commands_added"] = commands_added

        # Créer des skills si patterns répétés
        skills_created = create_skill_from_gaps(gaps)
        result["skills_created"] = skills_created

        # Ajouter des triggers alternatifs
        triggers_added = add_alternative_triggers(low_success)
        result["triggers_added"] = triggers_added
    except Exception as exc:
        log.error("Erreur Phase 2 : %s", exc)
        result["errors"].append(f"Phase 2: {exc}")

    # ── Phase 3 : Test ──
    log.info("[Phase 3] Vérification...")
    try:
        skills_ok = verify_skills_loadable()
        if not skills_ok:
            result["errors"].append("Phase 3: skills.json invalide")
    except Exception as exc:
        log.error("Erreur Phase 3 : %s", exc)
        result["errors"].append(f"Phase 3: {exc}")

    # ── Phase 4 : Log ──
    duration = round(time.time() - t0, 2)
    result["duration_s"] = duration
    log_cycle(result)

    # ── Résumé ──
    log.info(
        "═══ Résumé cycle %d : %d gaps, +%d commandes, +%d skills, +%d triggers, %.1fs ═══",
        cycle_num,
        result["gaps_found"],
        result["commands_added"],
        result["skills_created"],
        result["triggers_added"],
        duration,
    )
    if result["errors"]:
        log.warning("  Erreurs : %s", "; ".join(result["errors"]))

    return result


def main():
    parser = argparse.ArgumentParser(description="JARVIS Mega Improvement Loop")
    parser.add_argument(
        "--max-cycles", type=int, default=0,
        help="Nombre max de cycles (0 = illimité)",
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Pause entre les cycles en secondes (défaut: 30)",
    )
    args = parser.parse_args()

    # Écrire le PID file
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        log.info("PID %d écrit dans %s", os.getpid(), PID_FILE)
    except Exception as exc:
        log.warning("Impossible d'écrire le PID file : %s", exc)

    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║  JARVIS Mega Improvement Loop — Démarrage                  ║")
    log.info("║  Max cycles : %s | Intervalle : %ds                  ║",
             str(args.max_cycles) if args.max_cycles else "∞", args.interval)
    log.info("╚══════════════════════════════════════════════════════════════╝")

    cycle = 0
    try:
        while _running:
            cycle += 1

            if args.max_cycles and cycle > args.max_cycles:
                log.info("Nombre max de cycles atteint (%d). Arrêt.", args.max_cycles)
                break

            try:
                run_cycle(cycle)
            except Exception as exc:
                log.error("Erreur fatale cycle %d : %s\n%s", cycle, exc, traceback.format_exc())

            # ── Phase 5 : Pause ──
            if _running and (not args.max_cycles or cycle < args.max_cycles):
                log.info("Pause de %ds avant le prochain cycle...", args.interval)
                # Pause interruptible
                for _ in range(args.interval):
                    if not _running:
                        break
                    time.sleep(1)
    finally:
        # Nettoyage
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass
        log.info("Mega Improvement Loop terminé après %d cycles.", cycle)


if __name__ == "__main__":
    main()
