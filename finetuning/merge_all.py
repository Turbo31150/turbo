"""
JARVIS Fine-Tuning — Fusion et Reequilibrage du Dataset
=========================================================
Fusionne tous les datasets enrichis et reequilibre le ratio
JARVIS-specifique vs generique pour un fine-tuning optimal.

Strategie de reequilibrage:
- Exemples JARVIS (commandes, skills, outils, CoT): x3 oversampling
- Exemples french_instruct generiques: sous-echantillonnage a 20K max
- Ratio cible: ~60% JARVIS / ~40% generique

Usage:
    uv run python finetuning/merge_all.py
"""

import json
import random
from pathlib import Path

TURBO_DIR = Path("F:/BUREAU/turbo")
DATASET_DIR = TURBO_DIR / "finetuning" / "dataset"

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


def load_jsonl(path: Path) -> list[dict]:
    """Charge un fichier JSONL."""
    if not path.exists():
        print(f"  [SKIP] {path.name} non trouve")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]
    print(f"  [OK] {len(data)} exemples depuis {path.name}")
    return data


def is_jarvis_specific(example: dict) -> bool:
    """Determine si un exemple est specifique a JARVIS ou generique.

    Ne regarde QUE le contenu user/assistant (pas le system prompt,
    car tous les exemples ont le meme system prompt JARVIS).
    """
    messages = example.get("messages", [])

    # Mots-cles JARVIS dans le contenu user/assistant uniquement
    jarvis_keywords = [
        "jarvis", "lm studio", "ollama", "cluster", "gpu", "vram",
        "trading", "mexc", "crypto", "pipeline", "vocal", "whisper",
        "powershell", "commande", "script", "launcher", "modele ia",
        "qwen", "deepseek", "telegram", "mcp", "tool_call",
        "<thinking>", "j'ouvre", "j'execute", "je lance",
        "navigateur", "raccourci", "notification", "scan",
        "sniper", "monitor", "trident", "bitcoin", "ethereum",
    ]

    for msg in messages:
        if msg.get("role") in ("user", "assistant"):
            content = msg.get("content", "").lower()
            for kw in jarvis_keywords:
                if kw in content:
                    return True

    return False


def oversample(data: list[dict], factor: int) -> list[dict]:
    """Duplique les exemples pour l'oversampling."""
    return data * factor


def main():
    print("=" * 60)
    print("JARVIS Fine-Tuning — Fusion et Reequilibrage")
    print("=" * 60)

    # === Charger tous les datasets ===
    print("\n[1/4] Chargement des datasets...")

    # Dataset principal (train)
    train_data = load_jsonl(DATASET_DIR / "jarvis_finetune_train.jsonl")
    eval_data = load_jsonl(DATASET_DIR / "jarvis_finetune_eval.jsonl")

    # Enrichissements
    cot_data = load_jsonl(DATASET_DIR / "jarvis_cot.jsonl")
    multistep_data = load_jsonl(DATASET_DIR / "jarvis_augmented_multistep.jsonl")
    trading_data = load_jsonl(DATASET_DIR / "jarvis_trading_augmented.jsonl")

    # === Separer JARVIS vs generique ===
    print("\n[2/4] Classification JARVIS vs generique...")

    jarvis_examples = []
    generic_examples = []

    for ex in train_data:
        if is_jarvis_specific(ex):
            jarvis_examples.append(ex)
        else:
            generic_examples.append(ex)

    print(f"  Train original: {len(jarvis_examples)} JARVIS + {len(generic_examples)} generiques")

    # Ajouter tous les enrichissements (tous JARVIS-specifiques)
    enrichments = cot_data + multistep_data + trading_data
    jarvis_examples.extend(enrichments)
    print(f"  + {len(enrichments)} exemples enrichis (CoT + multistep + trading)")

    # === Reequilibrage ===
    print("\n[3/4] Reequilibrage du dataset...")

    # Oversampling JARVIS x3
    jarvis_oversampled = oversample(jarvis_examples, 3)
    print(f"  JARVIS oversample x3: {len(jarvis_examples)} -> {len(jarvis_oversampled)}")

    # Sous-echantillonnage generique a 20K max
    max_generic = 20000
    if len(generic_examples) > max_generic:
        random.seed(42)
        generic_sampled = random.sample(generic_examples, max_generic)
        print(f"  Generique sous-echantillonne: {len(generic_examples)} -> {len(generic_sampled)}")
    else:
        generic_sampled = generic_examples
        print(f"  Generique: {len(generic_sampled)} (pas de sous-echantillonnage)")

    # Fusion
    final_train = jarvis_oversampled + generic_sampled
    random.seed(42)
    random.shuffle(final_train)

    ratio_jarvis = len(jarvis_oversampled) / len(final_train) * 100
    print(f"\n  Dataset final: {len(final_train)} exemples")
    print(f"  Ratio: {ratio_jarvis:.1f}% JARVIS / {100-ratio_jarvis:.1f}% generique")

    # === Sauvegarde ===
    print("\n[4/4] Sauvegarde...")

    train_path = DATASET_DIR / "jarvis_final_train.jsonl"
    eval_path = DATASET_DIR / "jarvis_final_eval.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for ex in final_train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # Eval: garder tel quel + ajouter quelques CoT
    final_eval = eval_data
    if cot_data:
        # Ajouter 10% des CoT en eval
        n_cot_eval = max(1, len(cot_data) // 10)
        final_eval = eval_data + cot_data[:n_cot_eval]

    with open(eval_path, "w", encoding="utf-8") as f:
        for ex in final_eval:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"Dataset final sauvegarde !")
    print(f"  Train : {train_path} ({len(final_train)} exemples)")
    print(f"  Eval  : {eval_path} ({len(final_eval)} exemples)")
    print(f"  JARVIS: {len(jarvis_oversampled)} ({ratio_jarvis:.1f}%)")
    print(f"  Generic: {len(generic_sampled)} ({100-ratio_jarvis:.1f}%)")
    print(f"{'='*60}")

    # Mettre a jour train.py pour pointer vers les nouveaux fichiers
    print(f"\n[INFO] Pour utiliser ce dataset, modifier train.py:")
    print(f"  TRAIN_FILE = DATASET_DIR / 'jarvis_final_train.jsonl'")
    print(f"  EVAL_FILE = DATASET_DIR / 'jarvis_final_eval.jsonl'")


if __name__ == "__main__":
    main()
