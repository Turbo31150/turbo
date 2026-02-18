"""
JARVIS Fine-Tuning — Evaluation du modele fine-tune
=====================================================
Charge le modele de base + LoRA adapters depuis le dernier checkpoint,
teste sur un ensemble de phrases JARVIS typiques, compare avec les
reponses attendues, et affiche un rapport detaille avec score.

Pre-requis:
    - Arreter LM Studio pour liberer la VRAM
    - Avoir lance train.py (checkpoint dans output/)
    - GPU: ~40 GB VRAM totale necessaire

Usage:
    uv run python finetuning/evaluate.py
    uv run python finetuning/evaluate.py --base-only       (modele de base sans LoRA)
    uv run python finetuning/evaluate.py --checkpoint PATH  (checkpoint specifique)
    uv run python finetuning/evaluate.py --max-new-tokens 256
"""

import os
import sys
import json
import time
import argparse
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

import torch

# === CHEMINS ===
TURBO_DIR = Path("F:/BUREAU/turbo")
FINETUNING_DIR = TURBO_DIR / "finetuning"
OUTPUT_DIR = FINETUNING_DIR / "output"
RESULTS_DIR = FINETUNING_DIR / "assessment_results"

# === MODELE ===
MODEL_NAME = "Qwen/Qwen3-30B-A3B"

# === SYSTEM PROMPT JARVIS (meme que dans prepare_dataset.py) ===
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

# === GENERATION PARAMS ===
DEFAULT_MAX_NEW_TOKENS = 200
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = 0.9
DEFAULT_REPETITION_PENALTY = 1.1


# ============================================================================
#  BENCHMARK : 40 cas de test couvrant toutes les categories JARVIS
# ============================================================================

TEST_CASES = [
    # -----------------------------------------------------------------------
    #  CATEGORIE 1 : Commandes vocales (ouverture d'apps, actions systeme)
    # -----------------------------------------------------------------------
    {
        "id": "cmd_01",
        "category": "commande_vocale",
        "input": "ouvre chrome",
        "expected_keywords": ["ouvre", "chrome", "navigateur"],
        "expected_intent": "app_open",
        "description": "Ouverture de Google Chrome",
    },
    {
        "id": "cmd_02",
        "category": "commande_vocale",
        "input": "status du cluster",
        "expected_keywords": ["cluster", "status", "gpu", "modele", "lm studio"],
        "expected_intent": "cluster_status",
        "description": "Verification du status du cluster IA",
    },
    {
        "id": "cmd_03",
        "category": "commande_vocale",
        "input": "scan MEXC",
        "expected_keywords": ["scan", "mexc", "trading", "crypto", "paire"],
        "expected_intent": "trading_scan",
        "description": "Lancement d'un scan MEXC Futures",
    },
    {
        "id": "cmd_04",
        "category": "commande_vocale",
        "input": "ouvre le terminal",
        "expected_keywords": ["terminal", "ouvre", "powershell", "cmd"],
        "expected_intent": "app_open",
        "description": "Ouverture du terminal",
    },
    {
        "id": "cmd_05",
        "category": "commande_vocale",
        "input": "ferme tout",
        "expected_keywords": ["ferme", "tout", "application", "fenetre"],
        "expected_intent": "system_action",
        "description": "Fermeture de toutes les fenetres",
    },
    {
        "id": "cmd_06",
        "category": "commande_vocale",
        "input": "lance le pipeline intensif",
        "expected_keywords": ["pipeline", "intensif", "lance", "demarre"],
        "expected_intent": "pipeline",
        "description": "Lancement du pipeline intensif de trading",
    },
    {
        "id": "cmd_07",
        "category": "commande_vocale",
        "input": "redemarre le cluster",
        "expected_keywords": ["redemarr", "cluster", "lm studio", "relance"],
        "expected_intent": "cluster_action",
        "description": "Redemarrage du cluster LM Studio",
    },
    {
        "id": "cmd_08",
        "category": "commande_vocale",
        "input": "ouvre discord",
        "expected_keywords": ["ouvre", "discord"],
        "expected_intent": "app_open",
        "description": "Ouverture de Discord",
    },

    # -----------------------------------------------------------------------
    #  CATEGORIE 2 : Corrections vocales (transcription erronee -> corrigee)
    # -----------------------------------------------------------------------
    {
        "id": "corr_01",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "ouvres crom"',
        "expected_keywords": ["ouvre", "chrome"],
        "expected_intent": "correction",
        "description": "ouvres crom -> ouvre chrome",
    },
    {
        "id": "corr_02",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "statu du clustair"',
        "expected_keywords": ["status", "cluster"],
        "expected_intent": "correction",
        "description": "statu du clustair -> status du cluster",
    },
    {
        "id": "corr_03",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "skan mex c"',
        "expected_keywords": ["scan", "mexc"],
        "expected_intent": "correction",
        "description": "skan mex c -> scan MEXC",
    },
    {
        "id": "corr_04",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "lance le pipeligne"',
        "expected_keywords": ["lance", "pipeline"],
        "expected_intent": "correction",
        "description": "pipeligne -> pipeline",
    },
    {
        "id": "corr_05",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "ouvre le terminale"',
        "expected_keywords": ["ouvre", "terminal"],
        "expected_intent": "correction",
        "description": "terminale -> terminal",
    },
    {
        "id": "corr_06",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "mon te le sont"',
        "expected_keywords": ["monte", "son"],
        "expected_intent": "correction",
        "description": "mon te le sont -> monte le son",
    },
    {
        "id": "corr_07",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "anvoie sur telegrame"',
        "expected_keywords": ["envoie", "telegram"],
        "expected_intent": "correction",
        "description": "anvoie sur telegrame -> envoie sur Telegram",
    },
    {
        "id": "corr_08",
        "category": "correction_vocale",
        "input": 'Corrige cette transcription vocale : "fer me tou"',
        "expected_keywords": ["ferme", "tout"],
        "expected_intent": "correction",
        "description": "fer me tou -> ferme tout",
    },

    # -----------------------------------------------------------------------
    #  CATEGORIE 3 : Tool routing (quelle action/outil utiliser)
    # -----------------------------------------------------------------------
    {
        "id": "tool_01",
        "category": "tool_routing",
        "input": "monte le son",
        "expected_keywords": ["volume", "son", "monte", "augment"],
        "expected_intent": "system_volume",
        "description": "Augmentation du volume systeme",
    },
    {
        "id": "tool_02",
        "category": "tool_routing",
        "input": "envoie sur Telegram",
        "expected_keywords": ["telegram", "envo", "message"],
        "expected_intent": "send_message",
        "description": "Envoi d'un message Telegram",
    },
    {
        "id": "tool_03",
        "category": "tool_routing",
        "input": "prends une capture d'ecran",
        "expected_keywords": ["capture", "ecran", "screenshot"],
        "expected_intent": "screenshot",
        "description": "Prise de capture d'ecran",
    },
    {
        "id": "tool_04",
        "category": "tool_routing",
        "input": "quel est l'espace disque libre",
        "expected_keywords": ["disque", "espace", "libre", "stockage"],
        "expected_intent": "system_info",
        "description": "Verification de l'espace disque",
    },
    {
        "id": "tool_05",
        "category": "tool_routing",
        "input": "charge le modele deepseek sur le cluster",
        "expected_keywords": ["charge", "modele", "deepseek", "cluster", "lm studio"],
        "expected_intent": "model_load",
        "description": "Chargement d'un modele sur le cluster",
    },
    {
        "id": "tool_06",
        "category": "tool_routing",
        "input": "analyse technique sur BTC",
        "expected_keywords": ["analyse", "technique", "btc", "bitcoin", "trading"],
        "expected_intent": "trading_analysis",
        "description": "Analyse technique crypto",
    },
    {
        "id": "tool_07",
        "category": "tool_routing",
        "input": "mets en pause la musique",
        "expected_keywords": ["pause", "musique", "media"],
        "expected_intent": "media_control",
        "description": "Controle media — pause",
    },
    {
        "id": "tool_08",
        "category": "tool_routing",
        "input": "eteins l'ecran",
        "expected_keywords": ["ecran", "etein", "veille", "moniteur"],
        "expected_intent": "system_action",
        "description": "Mise en veille de l'ecran",
    },

    # -----------------------------------------------------------------------
    #  CATEGORIE 4 : Questions generales en francais
    # -----------------------------------------------------------------------
    {
        "id": "gen_01",
        "category": "question_generale",
        "input": "Explique-moi ce qu'est le machine learning en quelques mots",
        "expected_keywords": ["machine learning", "apprentissage", "donnee", "modele", "algorithme"],
        "expected_intent": "knowledge",
        "description": "Explication du machine learning",
    },
    {
        "id": "gen_02",
        "category": "question_generale",
        "input": "Quelle est la difference entre Python et JavaScript ?",
        "expected_keywords": ["python", "javascript", "langage", "programm"],
        "expected_intent": "knowledge",
        "description": "Comparaison de langages de programmation",
    },
    {
        "id": "gen_03",
        "category": "question_generale",
        "input": "Comment fonctionne un transformer en IA ?",
        "expected_keywords": ["transformer", "attention", "modele", "couche", "token"],
        "expected_intent": "knowledge",
        "description": "Explication des transformers",
    },
    {
        "id": "gen_04",
        "category": "question_generale",
        "input": "C'est quoi le fine-tuning d'un modele ?",
        "expected_keywords": ["fine-tuning", "modele", "entra", "adapt", "donnee"],
        "expected_intent": "knowledge",
        "description": "Explication du fine-tuning",
    },
    {
        "id": "gen_05",
        "category": "question_generale",
        "input": "Donne-moi 3 conseils pour bien coder en Python",
        "expected_keywords": ["python", "conseil", "code", "bonne pratique"],
        "expected_intent": "knowledge",
        "description": "Conseils de programmation Python",
    },
    {
        "id": "gen_06",
        "category": "question_generale",
        "input": "Quelle est la capitale de la France ?",
        "expected_keywords": ["paris", "france", "capitale"],
        "expected_intent": "knowledge",
        "description": "Question de culture generale simple",
    },
    {
        "id": "gen_07",
        "category": "question_generale",
        "input": "Explique le trading de futures crypto a un debutant",
        "expected_keywords": ["futures", "crypto", "trading", "levier", "position", "contrat"],
        "expected_intent": "knowledge",
        "description": "Explication du trading futures",
    },
    {
        "id": "gen_08",
        "category": "question_generale",
        "input": "Qu'est-ce qu'un GPU et pourquoi c'est important pour l'IA ?",
        "expected_keywords": ["gpu", "carte graphique", "calcul", "parall", "ia", "entra"],
        "expected_intent": "knowledge",
        "description": "Explication GPU et IA",
    },

    # -----------------------------------------------------------------------
    #  CATEGORIE 5 : Conversations JARVIS (meta, identite, contexte)
    # -----------------------------------------------------------------------
    {
        "id": "meta_01",
        "category": "conversation_jarvis",
        "input": "Qui es-tu ?",
        "expected_keywords": ["jarvis", "assistant", "vocal", "francais"],
        "expected_intent": "identity",
        "description": "Question d'identite JARVIS",
    },
    {
        "id": "meta_02",
        "category": "conversation_jarvis",
        "input": "Quels outils tu as a ta disposition ?",
        "expected_keywords": ["outil", "commande", "cluster", "trading", "systeme", "windows"],
        "expected_intent": "capabilities",
        "description": "Question sur les capacites JARVIS",
    },
    {
        "id": "meta_03",
        "category": "conversation_jarvis",
        "input": "Combien de GPU sont connectes au cluster ?",
        "expected_keywords": ["gpu", "cluster", "vram"],
        "expected_intent": "cluster_info",
        "description": "Question sur le hardware du cluster",
    },
    {
        "id": "meta_04",
        "category": "conversation_jarvis",
        "input": "Donne-moi un resume de tes capacites en trading",
        "expected_keywords": ["trading", "mexc", "scan", "analyse", "crypto", "position"],
        "expected_intent": "capabilities",
        "description": "Resume des capacites trading",
    },
]


# ============================================================================
#  DETECTION GPU
# ============================================================================

def check_gpu() -> dict:
    """Verifie les GPUs et retourne max_memory par device."""
    if not torch.cuda.is_available():
        print("[ERREUR] CUDA non disponible !")
        sys.exit(1)

    n = torch.cuda.device_count()
    print(f"\nGPUs detectes: {n}")

    max_memory = {}
    total = 0.0
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        # IMPORTANT: total_memory (PyTorch 2.10), PAS total_mem
        vram = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        total += vram
        max_memory[i] = f"{max(int(vram - 0.5), 1)}GiB"
        print(f"  GPU {i}: {name} — {vram:.1f} GB")

    max_memory["cpu"] = "32GiB"
    print(f"  Total VRAM: {total:.1f} GB\n")
    return max_memory


# ============================================================================
#  CHARGEMENT DU MODELE
# ============================================================================

def find_latest_checkpoint() -> Path | None:
    """Trouve le dernier checkpoint final dans output/."""
    if not OUTPUT_DIR.exists():
        return None

    runs = sorted(
        [p for p in OUTPUT_DIR.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        final = run / "final"
        if final.exists() and any(final.iterdir()):
            return final
        # Aussi chercher les checkpoint-XXXX
        checkpoints = sorted(
            [c for c in run.iterdir() if c.is_dir() and c.name.startswith("checkpoint-")],
            key=lambda c: int(c.name.split("-")[-1]) if c.name.split("-")[-1].isdigit() else 0,
            reverse=True,
        )
        if checkpoints:
            return checkpoints[0]

    return None


def load_model(max_memory: dict, adapter_path: Path | None = None):
    """Charge le modele de base en 4-bit + optionnel LoRA adapters."""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print(f"[...] Chargement {MODEL_NAME} en 4-bit...")
    t0 = time.time()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME, trust_remote_code=True, padding_side="left",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    # Verifier flash attention 2
    use_fa2 = False
    for i in range(torch.cuda.device_count()):
        if torch.cuda.get_device_capability(i)[0] >= 8:
            use_fa2 = True
            break

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        max_memory=max_memory,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        attn_implementation="flash_attention_2" if use_fa2 else "eager",
    )

    footprint = model.get_memory_footprint() / 1024**3
    elapsed = time.time() - t0
    print(f"[OK] Modele de base charge — {footprint:.1f} GB en {elapsed:.0f}s")

    # Charger LoRA adapters si fournis
    if adapter_path is not None:
        from peft import PeftModel

        print(f"[...] Chargement LoRA adapters: {adapter_path}")
        t1 = time.time()
        model = PeftModel.from_pretrained(model, str(adapter_path))
        model = model.merge_and_unload()
        elapsed2 = time.time() - t1
        print(f"[OK] LoRA merge en {elapsed2:.1f}s")

    model.config.use_cache = True  # Activer le cache KV pour l'inference
    return model, tokenizer


# ============================================================================
#  GENERATION
# ============================================================================

def generate_response(
    model,
    tokenizer,
    user_input: str,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
    repetition_penalty: float = DEFAULT_REPETITION_PENALTY,
) -> tuple[str, float]:
    """Genere une reponse du modele et retourne (texte, temps_generation)."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            do_sample=temperature > 0,
            pad_token_id=tokenizer.pad_token_id,
        )
    elapsed = time.time() - t0

    # Decoder seulement les nouveaux tokens
    new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    return response, elapsed


# ============================================================================
#  SCORING
# ============================================================================

def normalize_text(text: str) -> str:
    """Normalise un texte pour la comparaison (lowercase, sans accents, sans ponctuation)."""
    text = text.lower()
    # Supprimer les accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Supprimer la ponctuation
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def score_keyword_match(response: str, expected_keywords: list[str]) -> float:
    """Score de 0 a 1 base sur la presence des mots-cles attendus."""
    if not expected_keywords:
        return 1.0

    norm_response = normalize_text(response)
    matched = 0
    for keyword in expected_keywords:
        norm_kw = normalize_text(keyword)
        if norm_kw in norm_response:
            matched += 1

    return matched / len(expected_keywords)


def score_language_french(response: str) -> float:
    """Score de 0 a 1 verifiant que la reponse est bien en francais."""
    french_markers = [
        "je ", "tu ", "il ", "elle ", "nous ", "vous ", "les ", "des ", "une ",
        "est ", "sont ", "dans ", "pour ", "avec ", "sur ", "pas ", "que ",
        "qui ", "mais ", "ou ", "et ", "donc ", "car ", "comme ", "cette ",
        "ces ", "votre ", "notre ", "leur ", "c'est ", "j'", "l'", "d'",
        "du ", "au ", "aux ", "la ", "le ",
    ]
    norm = response.lower()
    if len(norm) < 10:
        return 0.5  # Trop court pour juger

    found = sum(1 for marker in french_markers if marker in norm)
    # Normaliser: si on trouve 5+ marqueurs, c'est clairement du francais
    return min(found / 5.0, 1.0)


def score_relevance(response: str, test_case: dict) -> float:
    """Score de pertinence global pour un cas de test."""
    if not response or len(response.strip()) < 3:
        return 0.0

    # 50% — mots-cles
    kw_score = score_keyword_match(response, test_case["expected_keywords"])

    # 30% — langue francaise
    fr_score = score_language_french(response)

    # 20% — longueur raisonnable (ni trop court, ni trop long)
    length = len(response)
    if length < 10:
        len_score = 0.2
    elif length < 30:
        len_score = 0.6
    elif length < 500:
        len_score = 1.0
    elif length < 1000:
        len_score = 0.8
    else:
        len_score = 0.5

    total = (kw_score * 0.50) + (fr_score * 0.30) + (len_score * 0.20)
    return round(total, 3)


# ============================================================================
#  EVALUATION
# ============================================================================

def run_tests(
    model,
    tokenizer,
    test_cases: list[dict],
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
) -> list[dict]:
    """Execute tous les tests et retourne les resultats detailles."""
    results = []
    total = len(test_cases)

    for i, tc in enumerate(test_cases, 1):
        print(f"\n  [{i:02d}/{total}] {tc['id']} — {tc['description']}")
        print(f"         Input: {tc['input'][:80]}...")

        try:
            response, gen_time = generate_response(
                model, tokenizer, tc["input"], max_new_tokens=max_new_tokens,
            )
        except Exception as e:
            response = f"[ERREUR] {e}"
            gen_time = 0.0

        score = score_relevance(response, tc)
        kw_score = score_keyword_match(response, tc["expected_keywords"])
        fr_score = score_language_french(response)

        # Afficher un apercu
        preview = response[:120].replace("\n", " ")
        status = "PASS" if score >= 0.5 else "FAIL"
        print(f"         Score: {score:.2f} (kw={kw_score:.2f} fr={fr_score:.2f}) [{status}]")
        print(f"         Reponse: {preview}...")
        print(f"         Temps: {gen_time:.1f}s")

        results.append({
            "id": tc["id"],
            "category": tc["category"],
            "description": tc["description"],
            "input": tc["input"],
            "expected_keywords": tc["expected_keywords"],
            "expected_intent": tc["expected_intent"],
            "response": response,
            "score": score,
            "keyword_score": kw_score,
            "french_score": fr_score,
            "generation_time_s": round(gen_time, 2),
            "status": status,
        })

    return results


# ============================================================================
#  RAPPORT
# ============================================================================

def print_report(results: list[dict], model_label: str):
    """Affiche un rapport d'assessment structure."""
    total = len(results)
    if total == 0:
        print("\n[WARN] Aucun resultat.")
        return

    # === Scores globaux ===
    avg_score = sum(r["score"] for r in results) / total
    avg_kw = sum(r["keyword_score"] for r in results) / total
    avg_fr = sum(r["french_score"] for r in results) / total
    avg_time = sum(r["generation_time_s"] for r in results) / total
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    print("\n")
    print("=" * 72)
    print(f"  RAPPORT D'EVALUATION — {model_label}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    print(f"\n  SCORE GLOBAL:       {avg_score:.3f} / 1.000")
    print(f"  Score mots-cles:    {avg_kw:.3f}")
    print(f"  Score francais:     {avg_fr:.3f}")
    print(f"  Reussis/Total:      {passed}/{total} ({100*passed/total:.0f}%)")
    print(f"  Echoues:            {failed}/{total}")
    print(f"  Temps moyen/reponse: {avg_time:.1f}s")

    # === Par categorie ===
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    print(f"\n  {'─' * 68}")
    print(f"  RESULTATS PAR CATEGORIE")
    print(f"  {'─' * 68}")

    cat_labels = {
        "commande_vocale": "Commandes vocales",
        "correction_vocale": "Corrections vocales",
        "tool_routing": "Tool routing",
        "question_generale": "Questions generales FR",
        "conversation_jarvis": "Conversations JARVIS",
    }

    for cat, cat_results in categories.items():
        n = len(cat_results)
        cat_avg = sum(r["score"] for r in cat_results) / n
        cat_passed = sum(1 for r in cat_results if r["status"] == "PASS")
        label = cat_labels.get(cat, cat)
        bar_filled = int(cat_avg * 20)
        bar = "#" * bar_filled + "." * (20 - bar_filled)
        print(f"\n  {label:<25} [{bar}] {cat_avg:.3f}  ({cat_passed}/{n} passes)")

        for r in cat_results:
            icon = "[OK]" if r["status"] == "PASS" else "[!!]"
            print(f"    {icon} {r['id']}: {r['description']:<40} score={r['score']:.2f}  ({r['generation_time_s']:.1f}s)")

    # === Pires resultats ===
    worst = sorted(results, key=lambda r: r["score"])[:5]
    if worst and worst[0]["score"] < 0.5:
        print(f"\n  {'─' * 68}")
        print(f"  POINTS A AMELIORER (5 pires scores)")
        print(f"  {'─' * 68}")
        for r in worst:
            print(f"    [{r['score']:.2f}] {r['id']}: {r['description']}")
            print(f"           Input:    {r['input'][:70]}")
            response_preview = r["response"][:100].replace("\n", " ")
            print(f"           Reponse:  {response_preview}")
            print(f"           Keywords: {', '.join(r['expected_keywords'])}")
            print()

    # === Meilleurs resultats ===
    best = sorted(results, key=lambda r: r["score"], reverse=True)[:5]
    print(f"  {'─' * 68}")
    print(f"  MEILLEURS RESULTATS (5 meilleurs scores)")
    print(f"  {'─' * 68}")
    for r in best:
        print(f"    [{r['score']:.2f}] {r['id']}: {r['description']}")

    print(f"\n{'=' * 72}")


def save_results(results: list[dict], model_label: str) -> Path:
    """Sauvegarde les resultats en JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^\w\-]", "_", model_label)
    filename = f"assessment_{safe_label}_{timestamp}.json"
    filepath = RESULTS_DIR / filename

    total = len(results)
    avg_score = sum(r["score"] for r in results) / total if total else 0
    passed = sum(1 for r in results if r["status"] == "PASS")

    report = {
        "model": model_label,
        "base_model": MODEL_NAME,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "avg_score": round(avg_score, 4),
            "avg_keyword_score": round(sum(r["keyword_score"] for r in results) / total, 4) if total else 0,
            "avg_french_score": round(sum(r["french_score"] for r in results) / total, 4) if total else 0,
            "avg_generation_time": round(sum(r["generation_time_s"] for r in results) / total, 2) if total else 0,
        },
        "results": results,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Resultats sauvegardes: {filepath}")
    return filepath


# ============================================================================
#  MAIN
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="JARVIS Fine-Tuning — Assessment du modele fine-tune",
    )
    parser.add_argument(
        "--base-only", action="store_true",
        help="Tester uniquement le modele de base (sans LoRA)",
    )
    parser.add_argument(
        "--checkpoint", type=str, default=None,
        help="Chemin vers un checkpoint specifique (dossier avec adapter_config.json)",
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=DEFAULT_MAX_NEW_TOKENS,
        help=f"Nombre max de tokens generes (defaut: {DEFAULT_MAX_NEW_TOKENS})",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Tester base ET fine-tune pour comparaison",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("\n" + "=" * 72)
    print("  JARVIS Fine-Tuning — Assessment")
    print(f"  Modele de base: {MODEL_NAME}")
    print(f"  Tests: {len(TEST_CASES)} cas")
    print("=" * 72)

    # GPU
    max_memory = check_gpu()

    # Determiner le checkpoint
    adapter_path = None
    model_label = "base"

    if not args.base_only:
        if args.checkpoint:
            adapter_path = Path(args.checkpoint)
            if not adapter_path.exists():
                print(f"[ERREUR] Checkpoint non trouve: {adapter_path}")
                sys.exit(1)
        else:
            adapter_path = find_latest_checkpoint()

        if adapter_path:
            model_label = f"fine-tune ({adapter_path.parent.name})"
            print(f"[OK] Checkpoint LoRA: {adapter_path}")
        else:
            print("[WARN] Aucun checkpoint trouve — test du modele de base uniquement")
            model_label = "base (pas de checkpoint)"

    # === Mode comparaison ===
    if args.compare:
        print(f"\n{'=' * 72}")
        print("  MODE COMPARAISON: Base vs Fine-tune")
        print(f"{'=' * 72}")

        # 1) Tester le modele de base
        print(f"\n[1/2] Test du modele de base...")
        model, tokenizer = load_model(max_memory, adapter_path=None)
        base_results = run_tests(model, tokenizer, TEST_CASES, args.max_new_tokens)
        print_report(base_results, "Modele de base (Qwen3-30B-A3B)")
        save_results(base_results, "base")

        # Liberer la memoire GPU
        del model
        torch.cuda.empty_cache()

        # 2) Tester le modele fine-tune
        if adapter_path:
            print(f"\n[2/2] Test du modele fine-tune...")
            model, tokenizer = load_model(max_memory, adapter_path=adapter_path)
            ft_results = run_tests(model, tokenizer, TEST_CASES, args.max_new_tokens)
            print_report(ft_results, f"Modele fine-tune ({adapter_path.parent.name})")
            save_results(ft_results, "fine-tune")

            # Comparaison
            print(f"\n{'=' * 72}")
            print("  COMPARAISON BASE vs FINE-TUNE")
            print(f"{'=' * 72}")

            base_avg = sum(r["score"] for r in base_results) / len(base_results)
            ft_avg = sum(r["score"] for r in ft_results) / len(ft_results)
            delta = ft_avg - base_avg
            arrow = "+" if delta > 0 else ("-" if delta < 0 else "=")

            print(f"\n  Score base:       {base_avg:.3f}")
            print(f"  Score fine-tune:  {ft_avg:.3f}")
            print(f"  Delta:            {delta:+.3f} [{arrow}]")
            print()

            # Par categorie
            base_by_cat = {}
            ft_by_cat = {}
            for r in base_results:
                base_by_cat.setdefault(r["category"], []).append(r["score"])
            for r in ft_results:
                ft_by_cat.setdefault(r["category"], []).append(r["score"])

            cat_labels = {
                "commande_vocale": "Commandes vocales",
                "correction_vocale": "Corrections vocales",
                "tool_routing": "Tool routing",
                "question_generale": "Questions generales",
                "conversation_jarvis": "Conversations JARVIS",
            }

            print(f"  {'Categorie':<25} {'Base':>8} {'FT':>8} {'Delta':>8}")
            print(f"  {'─' * 51}")
            for cat in base_by_cat:
                b = sum(base_by_cat[cat]) / len(base_by_cat[cat])
                ft_scores = ft_by_cat.get(cat, [0])
                f_ = sum(ft_scores) / max(len(ft_scores), 1)
                d = f_ - b
                a = "+" if d > 0 else ("-" if d < 0 else "=")
                label = cat_labels.get(cat, cat)
                print(f"  {label:<25} {b:>7.3f}  {f_:>7.3f}  {d:>+7.3f} [{a}]")

            del model
            torch.cuda.empty_cache()
        else:
            print("\n[SKIP] Pas de checkpoint — comparaison impossible")

        print(f"\n{'=' * 72}")
        print("  Assessment termine.")
        print(f"{'=' * 72}")
        return

    # === Mode normal (un seul modele) ===
    model, tokenizer = load_model(max_memory, adapter_path=adapter_path)

    print(f"\n[>>>] Assessment en cours ({model_label})...\n")
    results = run_tests(model, tokenizer, TEST_CASES, args.max_new_tokens)

    # Rapport
    print_report(results, model_label)

    # Sauvegarder
    filepath = save_results(results, model_label)

    # Cleanup
    del model
    torch.cuda.empty_cache()

    print(f"\n[DONE] Assessment termine — {filepath}")
    print(f"[NEXT] Pour comparer base vs fine-tune: uv run python finetuning/evaluate.py --compare")


if __name__ == "__main__":
    main()
