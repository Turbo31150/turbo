"""
JARVIS Fine-Tuning — Preparation du Dataset
=============================================
Extrait les donnees JARVIS (commands, skills, scenarios, corrections)
et les fusionne avec angeluriot/french_instruct pour creer un dataset
de fine-tuning au format ChatML pour SFT.

Usage:
    uv run python finetuning/prepare_dataset.py [max_hf_samples]
    uv run python finetuning/prepare_dataset.py 50000
"""

import json
import sqlite3
import random
import sys
from pathlib import Path

# === CHEMINS ===
TURBO_DIR = Path("F:/BUREAU/turbo")
DATA_DIR = TURBO_DIR / "data"
DB_PATH = DATA_DIR / "jarvis.db"
ETOILE_DB_PATH = DATA_DIR / "etoile.db"
COMMANDS_JSON = DATA_DIR / "jarvis_commands_compact.json"
SKILLS_JSON = DATA_DIR / "skills.json"
OUTPUT_DIR = TURBO_DIR / "finetuning" / "dataset"

# === SYSTEM PROMPT JARVIS ===
SYSTEM_PROMPT = (
    "Tu es JARVIS, un assistant vocal intelligent en francais. "
    "Tu controles un systeme Windows avec des commandes vocales, "
    "tu geres un cluster de modeles d'IA locale (LM Studio, Ollama), "
    "tu analyses les marches de trading crypto sur MEXC Futures, "
    "et tu assistes l'utilisateur dans toutes ses taches quotidiennes. "
    "Tu es concis, precis et naturel. Tu reponds toujours en francais. "
    "Tu executes les commandes sans hesiter quand tu es sur de l'intention. "
    "Tu demandes confirmation uniquement pour les actions destructives ou ambigues."
)


# ========== CHARGEMENT DES DONNEES ==========

def load_commands_from_db() -> list[dict]:
    """Charge les commandes depuis SQLite."""
    if not DB_PATH.exists():
        print(f"  [WARN] DB non trouvee: {DB_PATH}")
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM commands").fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} commandes depuis DB")
    return rows


def load_commands_from_json() -> list[dict]:
    """Charge les commandes depuis le JSON compact (fallback)."""
    if not COMMANDS_JSON.exists():
        print(f"  [WARN] JSON non trouve: {COMMANDS_JSON}")
        return []
    with open(COMMANDS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    commands = data if isinstance(data, list) else data.get("commands", [])
    print(f"  [OK] {len(commands)} commandes depuis JSON")
    return commands


def load_skills() -> list[dict]:
    """Charge les skills depuis le JSON."""
    if not SKILLS_JSON.exists():
        print(f"  [WARN] Skills non trouve: {SKILLS_JSON}")
        return []
    with open(SKILLS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    skills = data if isinstance(data, list) else data.get("skills", [])
    print(f"  [OK] {len(skills)} skills depuis JSON")
    return skills


def load_scenarios() -> list[dict]:
    """Charge les scenarios de validation depuis SQLite."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM scenarios").fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} scenarios depuis DB")
    return rows


def load_corrections() -> list[dict]:
    """Charge les corrections vocales depuis SQLite."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM voice_corrections").fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} corrections vocales depuis DB")
    return rows


# ========== CONVERSION EN CONVERSATIONS ==========

def _parse_json_field(value) -> list:
    """Parse un champ JSON string ou retourne la liste directement."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [value] if value.strip() else []
    return []


def _make_conv(user_msg: str, assistant_msg: str) -> dict:
    """Cree une conversation ChatML standard."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg.strip()},
            {"role": "assistant", "content": assistant_msg.strip()},
        ]
    }


def _action_response(name: str, category: str, description: str, action_type: str, action: str) -> str:
    """Construit une reponse naturelle pour une commande."""
    prefixes = {
        "app_open": "J'ouvre",
        "browser": "J'ouvre dans le navigateur",
        "powershell": "J'execute",
        "hotkey": "J'envoie le raccourci",
        "script": "Je lance le script",
        "pipeline": "Je demarre le pipeline",
        "jarvis_tool": "J'utilise l'outil",
    }
    prefix = prefixes.get(action_type, "J'execute")

    if action_type in ("app_open", "browser"):
        return f"{prefix} {description.lower().rstrip('.')}."
    if action_type == "hotkey":
        return f"{description.rstrip('.')}. {prefix} {action}."
    if action_type == "pipeline":
        return f"Je lance le pipeline : {description.lower().rstrip('.')}."
    return f"{description.rstrip('.')}."


def commands_to_conversations(commands: list[dict]) -> list[dict]:
    """Convertit les commandes en paires trigger -> reponse."""
    convs = []
    for cmd in commands:
        triggers = _parse_json_field(cmd.get("triggers", []))
        description = cmd.get("description", "")
        if not triggers or not description:
            continue

        response = _action_response(
            cmd.get("name", ""),
            cmd.get("category", ""),
            description,
            cmd.get("action_type", ""),
            cmd.get("action", ""),
        )

        for trigger in triggers:
            t = trigger.strip()
            if t:
                convs.append(_make_conv(t, response))

    print(f"  [OK] {len(convs)} conversations depuis commandes")
    return convs


def skills_to_conversations(skills: list[dict]) -> list[dict]:
    """Convertit les skills en conversations avec etapes."""
    convs = []
    for skill in skills:
        triggers = _parse_json_field(skill.get("triggers", []))
        steps = _parse_json_field(skill.get("steps", []))
        description = skill.get("description", "")
        if not triggers or not steps:
            continue

        steps_lines = []
        for i, step in enumerate(steps, 1):
            if isinstance(step, dict):
                desc = step.get("description", step.get("tool", f"etape {i}"))
            else:
                desc = str(step)
            steps_lines.append(f"{i}. {desc}")

        response = f"{description}\n\nPipeline en {len(steps)} etapes :\n" + "\n".join(steps_lines)

        for trigger in triggers:
            t = trigger.strip()
            if t:
                convs.append(_make_conv(t, response))

    print(f"  [OK] {len(convs)} conversations depuis skills")
    return convs


def scenarios_to_conversations(scenarios: list[dict]) -> list[dict]:
    """Convertit les scenarios de validation en conversations."""
    convs = []
    for sc in scenarios:
        voice = sc.get("voice_input", "").strip()
        result = sc.get("expected_result", "").strip()
        if voice and result:
            convs.append(_make_conv(voice, result))

    print(f"  [OK] {len(convs)} conversations depuis scenarios")
    return convs


def corrections_to_conversations(corrections: list[dict]) -> list[dict]:
    """Convertit les corrections vocales en paires de correction."""
    convs = []
    for corr in corrections:
        wrong = corr.get("wrong", "").strip()
        correct = corr.get("correct", "").strip()
        if wrong and correct and wrong != correct:
            convs.append(_make_conv(
                f'Corrige cette transcription vocale : "{wrong}"',
                f'La transcription corrigee est : "{correct}".',
            ))

    print(f"  [OK] {len(convs)} conversations depuis corrections vocales")
    return convs


# ========== ETOILE.DB — DONNEES ENRICHIES ==========

def load_pipeline_dictionary() -> list[dict]:
    """Charge pipeline_dictionary depuis etoile.db (2658+ entries)."""
    if not ETOILE_DB_PATH.exists():
        print(f"  [WARN] etoile.db non trouvee: {ETOILE_DB_PATH}")
        return []
    conn = sqlite3.connect(str(ETOILE_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT pipeline_id, trigger_phrase, steps, category, action_type "
        "FROM pipeline_dictionary WHERE trigger_phrase IS NOT NULL"
    ).fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} pipeline_dictionary depuis etoile.db")
    return rows


def pipeline_dict_to_conversations(entries: list[dict]) -> list[dict]:
    """Convertit pipeline_dictionary en conversations."""
    convs = []
    for e in entries:
        trigger = (e.get("trigger_phrase") or "").strip()
        pipeline_id = (e.get("pipeline_id") or "").strip()
        category = (e.get("category") or "").strip()
        action_type = (e.get("action_type") or "").strip()
        steps = (e.get("steps") or "").strip()
        if not trigger:
            continue

        # Build a natural response
        desc = pipeline_id.replace("_", " ")
        if action_type == "app_open":
            resp = f"J'ouvre {desc}."
        elif action_type == "browser":
            resp = f"J'ouvre dans le navigateur : {desc}."
        elif action_type == "powershell":
            resp = f"J'execute la commande : {desc}."
        elif action_type == "pipeline":
            resp = f"Je lance le pipeline : {desc}."
        elif action_type == "hotkey":
            resp = f"J'envoie le raccourci : {steps or desc}."
        else:
            resp = f"J'execute : {desc}."

        if category:
            resp += f" [categorie: {category}]"

        convs.append(_make_conv(trigger, resp))

    print(f"  [OK] {len(convs)} conversations depuis pipeline_dictionary")
    return convs


def load_domino_chains() -> list[dict]:
    """Charge domino_chains depuis etoile.db (835+ entries)."""
    if not ETOILE_DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(ETOILE_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT trigger_cmd, condition, next_cmd, delay_ms, auto, description "
        "FROM domino_chains"
    ).fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} domino_chains depuis etoile.db")
    return rows


def domino_chains_to_conversations(chains: list[dict]) -> list[dict]:
    """Convertit domino_chains en conversations d'explication de cascades."""
    # Group by trigger_cmd
    triggers: dict[str, list[dict]] = {}
    for c in chains:
        t = c.get("trigger_cmd", "")
        triggers.setdefault(t, []).append(c)

    convs = []
    for trigger, entries in triggers.items():
        if not trigger:
            continue
        # Build cascade explanation
        steps_desc = []
        for e in entries[:5]:  # Max 5 per trigger
            cond = e.get("condition", "always")
            next_cmd = e.get("next_cmd", "")
            desc = e.get("description", "")
            delay = e.get("delay_ms", 0)
            step = f"Si {cond}: {next_cmd}"
            if delay:
                step += f" (delai {delay}ms)"
            if desc:
                step += f" — {desc}"
            steps_desc.append(step)

        cascade_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps_desc))
        resp = f"La cascade '{trigger}' execute les etapes suivantes :\n{cascade_text}"

        convs.append(_make_conv(
            f"Explique la cascade {trigger}",
            resp,
        ))

        # Also add execution trigger
        first_desc = entries[0].get("description", f"cascade {trigger}")
        convs.append(_make_conv(
            f"Lance la cascade {trigger}",
            f"Je lance la cascade : {first_desc}. {len(entries)} etapes a executer.",
        ))

    print(f"  [OK] {len(convs)} conversations depuis domino_chains")
    return convs


def load_etoile_corrections() -> list[dict]:
    """Charge voice_corrections depuis etoile.db (2628+ entries)."""
    if not ETOILE_DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(ETOILE_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT wrong, correct, category FROM voice_corrections"
    ).fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} voice_corrections depuis etoile.db")
    return rows


def etoile_corrections_to_conversations(corrections: list[dict]) -> list[dict]:
    """Convertit etoile.db voice_corrections en paires de correction."""
    convs = []
    seen = set()
    for corr in corrections:
        wrong = (corr.get("wrong") or "").strip()
        correct = (corr.get("correct") or "").strip()
        if wrong and correct and wrong != correct:
            key = f"{wrong}|{correct}"
            if key not in seen:
                seen.add(key)
                convs.append(_make_conv(
                    f'Corrige cette transcription vocale : "{wrong}"',
                    f'La transcription corrigee est : "{correct}".',
                ))

    print(f"  [OK] {len(convs)} conversations depuis etoile corrections (dedup)")
    return convs


def load_scenario_weights() -> list[dict]:
    """Charge scenario_weights depuis etoile.db (227 entries)."""
    if not ETOILE_DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(ETOILE_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT scenario, agent, weight, priority, chain_next, description "
        "FROM scenario_weights"
    ).fetchall()]
    conn.close()
    print(f"  [OK] {len(rows)} scenario_weights depuis etoile.db")
    return rows


def scenario_weights_to_conversations(weights: list[dict]) -> list[dict]:
    """Convertit scenario_weights en conversations de routing IA."""
    # Group by scenario
    scenarios: dict[str, list[dict]] = {}
    for w in weights:
        s = w.get("scenario", "")
        scenarios.setdefault(s, []).append(w)

    convs = []
    for scenario, agents in scenarios.items():
        if not scenario:
            continue
        agents.sort(key=lambda a: a.get("priority", 99))
        routing = []
        for a in agents:
            agent = a.get("agent", "")
            weight = a.get("weight", 1.0)
            chain = a.get("chain_next", "")
            routing.append(f"{agent} (poids={weight}" + (f", chain={chain}" if chain else "") + ")")

        resp = (
            f"Pour le scenario '{scenario.replace('_', ' ')}', "
            f"le routing optimal est : {' → '.join(routing)}."
        )
        desc = agents[0].get("description", "")
        if desc:
            resp += f" {desc}"

        convs.append(_make_conv(
            f"Quel agent utiliser pour {scenario.replace('_', ' ')} ?",
            resp,
        ))

    print(f"  [OK] {len(convs)} conversations depuis scenario_weights")
    return convs


def download_french_instruct(max_samples: int = 50000) -> list[dict]:
    """Telecharge angeluriot/french_instruct depuis HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [WARN] 'datasets' non installe — skip french_instruct")
        return []

    print(f"  [...] Telechargement angeluriot/french_instruct ({max_samples} max)...")
    try:
        ds = load_dataset("angeluriot/french_instruct", split=f"train[:{max_samples}]")
    except Exception as e:
        print(f"  [WARN] Erreur telechargement: {e}")
        return []

    convs = []
    for row in ds:
        messages = []

        # Format angeluriot/french_instruct: "conversation" (singulier) avec "text"
        if "conversation" in row:
            raw = row["conversation"]
            if isinstance(raw, list):
                for msg in raw:
                    role = msg.get("role", msg.get("from", "user"))
                    content = msg.get("text", msg.get("content", msg.get("value", "")))
                    if role in ("human", "user"):
                        role = "user"
                    elif role in ("gpt", "assistant", "model"):
                        role = "assistant"
                    elif role != "system":
                        continue
                    if content:
                        messages.append({"role": role, "content": content})

        # Format alternatif: "conversations" (pluriel)
        elif "conversations" in row:
            raw = row["conversations"]
            if isinstance(raw, list):
                for msg in raw:
                    role = msg.get("role", msg.get("from", "user"))
                    content = msg.get("text", msg.get("content", msg.get("value", "")))
                    if role in ("human", "user"):
                        role = "user"
                    elif role in ("gpt", "assistant", "model"):
                        role = "assistant"
                    elif role != "system":
                        continue
                    if content:
                        messages.append({"role": role, "content": content})

        elif "instruction" in row and "output" in row:
            instruction = row["instruction"]
            if row.get("input"):
                instruction = f"{instruction}\n\n{row['input']}"
            messages = [
                {"role": "user", "content": instruction},
                {"role": "assistant", "content": row["output"]},
            ]

        elif "question" in row and "answer" in row:
            messages = [
                {"role": "user", "content": row["question"]},
                {"role": "assistant", "content": row["answer"]},
            ]

        if len(messages) >= 2:
            if not messages or messages[0]["role"] != "system":
                messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
            convs.append({"messages": messages})

    print(f"  [OK] {len(convs)} conversations depuis french_instruct")
    return convs


# ========== SAUVEGARDE ==========

def save_dataset(conversations: list[dict], name: str = "jarvis_finetune"):
    """Sauvegarde en JSONL avec split train/eval 95/5."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    random.seed(42)
    random.shuffle(conversations)

    split = int(len(conversations) * 0.95)
    train_data = conversations[:split]
    eval_data = conversations[split:]

    train_path = OUTPUT_DIR / f"{name}_train.jsonl"
    eval_path = OUTPUT_DIR / f"{name}_eval.jsonl"

    for data, path in [(train_data, train_path), (eval_data, eval_path)]:
        with open(path, "w", encoding="utf-8") as f:
            for conv in data:
                f.write(json.dumps(conv, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"Dataset sauvegarde !")
    print(f"  Train : {train_path} ({len(train_data)} exemples)")
    print(f"  Eval  : {eval_path} ({len(eval_data)} exemples)")
    print(f"  Total : {len(conversations)} exemples")
    print(f"{'='*60}")


# ========== MAIN ==========

def main():
    print("=" * 60)
    print("JARVIS Fine-Tuning — Preparation du Dataset v2")
    print("  Sources: jarvis.db + etoile.db + HuggingFace")
    print("=" * 60)

    all_convs: list[dict] = []

    # 1. Commandes JARVIS (jarvis.db)
    print("\n[1/9] Commandes JARVIS (jarvis.db)...")
    commands = load_commands_from_db()
    if not commands:
        commands = load_commands_from_json()
    all_convs.extend(commands_to_conversations(commands))

    # 2. Skills (jarvis.db)
    print("\n[2/9] Skills JARVIS...")
    all_convs.extend(skills_to_conversations(load_skills()))

    # 3. Scenarios (jarvis.db)
    print("\n[3/9] Scenarios de validation...")
    all_convs.extend(scenarios_to_conversations(load_scenarios()))

    # 4. Corrections vocales (jarvis.db)
    print("\n[4/9] Corrections vocales (jarvis.db)...")
    all_convs.extend(corrections_to_conversations(load_corrections()))

    # 5. Pipeline Dictionary (etoile.db — 2658 entries)
    print("\n[5/9] Pipeline Dictionary (etoile.db)...")
    all_convs.extend(pipeline_dict_to_conversations(load_pipeline_dictionary()))

    # 6. Domino Chains (etoile.db — 835 entries)
    print("\n[6/9] Domino Chains (etoile.db)...")
    all_convs.extend(domino_chains_to_conversations(load_domino_chains()))

    # 7. Voice Corrections (etoile.db — 2628 entries, dedup)
    print("\n[7/9] Corrections vocales (etoile.db)...")
    all_convs.extend(etoile_corrections_to_conversations(load_etoile_corrections()))

    # 8. Scenario Weights / Routing IA (etoile.db — 227 entries)
    print("\n[8/9] Scenario Weights — Routing IA (etoile.db)...")
    all_convs.extend(scenario_weights_to_conversations(load_scenario_weights()))

    # 9. Dataset HuggingFace francais
    print("\n[9/9] Dataset HuggingFace francais...")
    max_hf = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    all_convs.extend(download_french_instruct(max_samples=max_hf))

    # Deduplication
    print(f"\n[DEDUP] Avant: {len(all_convs)} conversations")
    seen = set()
    unique = []
    for conv in all_convs:
        # Key = user message content
        msgs = conv.get("messages", [])
        user_msgs = [m["content"] for m in msgs if m["role"] == "user"]
        key = "|".join(user_msgs)
        if key not in seen:
            seen.add(key)
            unique.append(conv)
    all_convs = unique
    print(f"  Apres dedup: {len(all_convs)} conversations")

    # Sauvegarder
    print(f"\n[TOTAL] {len(all_convs)} conversations")
    save_dataset(all_convs, name="jarvis_final")


if __name__ == "__main__":
    main()
