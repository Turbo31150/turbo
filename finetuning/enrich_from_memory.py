"""
Enrichissement du dataset JARVIS avec la mémoire systeme + bases SQL.
Genere des exemples Q/A pour former le modele sur sa propre architecture.
"""
import json
import sqlite3
import os
from pathlib import Path

DATASET_DIR = Path("F:/BUREAU/turbo/finetuning/dataset")
TRAIN_FILE = DATASET_DIR / "jarvis_final_train.jsonl"
ENRICHMENT_FILE = DATASET_DIR / "jarvis_memory_enrichment.jsonl"

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

def make_example(user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }

def generate_cluster_examples() -> list:
    """Exemples sur l'architecture du cluster IA."""
    examples = []

    # Architecture generale
    examples.append(make_example(
        "Decris ton architecture cluster",
        "Mon cluster IA distribue comprend 6 noeuds :\n"
        "- M1 (10.5.0.2:1234) : qwen3-8b sur RTX 3080, PRIORITAIRE, 100% benchmark, 0.6-2.5s\n"
        "- M2 (192.168.1.26:1234) : deepseek-coder-v2-lite, 3 GPU 24GB, specialise code review\n"
        "- M3 (192.168.1.113:1234) : mistral-7b, 1 GPU 8GB, usage general\n"
        "- OL1 (127.0.0.1:11434) : Ollama, qwen3:1.7b local + cloud (minimax, glm-5)\n"
        "- GEMINI : Gemini 3 Pro via proxy, specialise architecture et vision\n"
        "- CLAUDE : Claude Code via proxy, raisonnement profond cloud\n"
        "Total : 10 GPU, environ 78 GB VRAM."
    ))

    examples.append(make_example(
        "Quel noeud est le plus rapide ?",
        "OL1 est le plus rapide pour les questions simples (0.5s avec qwen3:1.7b). "
        "M1 est le plus rapide pour les taches complexes (0.6-2.5s avec qwen3-8b, 65 tok/s). "
        "M1 est PRIORITAIRE dans la matrice de routage car il a obtenu 100% au benchmark."
    ))

    examples.append(make_example(
        "Comment fonctionne le consensus ?",
        "Le consensus utilise un vote pondere entre les agents :\n"
        "- M1 : poids 1.8 (PRIORITAIRE)\n"
        "- M2 : poids 1.4 (code review)\n"
        "- OL1 : poids 1.3 (vitesse)\n"
        "- GEMINI : poids 1.2 (architecture)\n"
        "- CLAUDE : poids 1.2 (raisonnement)\n"
        "- M3 : poids 1.0 (general)\n"
        "Quorum : somme(opinion * poids) / somme(poids) >= 0.65 pour valider une decision."
    ))

    examples.append(make_example(
        "Que faire si M1 est offline ?",
        "La chaine de fallback est : M1 -> M2 -> M3 -> OL1 -> GEMINI -> CLAUDE. "
        "Si M1 tombe, M2 prend le relai pour le code et le debug. "
        "Si M2 aussi est down, M3 assure les taches generales. "
        "OL1 reste disponible pour les questions rapides. "
        "En dernier recours, GEMINI ou CLAUDE cloud prennent la main."
    ))

    examples.append(make_example(
        "Comment router une tache de code ?",
        "Pour du code nouveau, la matrice de routage est :\n"
        "- Principal : M1 (qwen3-8b, 100% benchmark)\n"
        "- Secondaire : M2 (review deepseek-coder)\n"
        "- Verificateur : GEMINI (architecture)\n"
        "Pour un bug fix : M1 principal, M2 patch. "
        "Pour du refactoring : M1 principal, M2 validation. "
        "JAMAIS M3 pour le raisonnement — il n'est pas assez precis."
    ))

    examples.append(make_example(
        "Quels sont les GPU disponibles ?",
        "10 GPU repartis sur 3 machines :\n"
        "- Machine 1 (locale) : RTX 2060 12GB (GPU 0), 4x GTX 1660 Super 6GB (GPU 1-4), RTX 3080 10GB (GPU 5)\n"
        "- Machine 2 (192.168.1.26) : 3 GPU, 24GB total\n"
        "- Machine 3 (192.168.1.113) : 1 GPU, 8GB\n"
        "Total : ~78 GB VRAM. La 3080 est la plus puissante (8704 CUDA cores, 760 GB/s)."
    ))

    examples.append(make_example(
        "Comment appeler M1 ?",
        "M1 utilise LM Studio Responses API. Appel sans auth :\n"
        "curl -s http://127.0.0.1:1234/api/v1/chat -H 'Content-Type: application/json' "
        "-d '{\"model\":\"qwen3-8b\",\"input\":\"/nothink\\nTon prompt\",\"temperature\":0.2,"
        "\"max_output_tokens\":1024,\"stream\":false,\"store\":false}'\n"
        "IMPORTANT : prefixer /nothink pour eviter le thinking cache de Qwen3. "
        "Extraire le dernier element type=message dans output[]."
    ))

    examples.append(make_example(
        "Quel modele utiliser pour le trading ?",
        "Pour le trading, le pipeline GPU v2.3 utilise 6 IA en consensus :\n"
        "- M3 (w=1.0), GEMINI (w=1.1), OL1-cloud (w=1.3), M1 (w=1.5), M2 (w=1.2), OL1-local (w=0.8)\n"
        "OL1-cloud (minimax) fait la recherche web en temps reel. "
        "M1 analyse les signaux techniques. "
        "100 strategies : breakout(20), reversal(20), momentum(20), mean_reversion(20), order_book(20). "
        "Permission : consensus>=60% ET confiance>=50% ET spread>20%."
    ))

    return examples


def generate_system_examples() -> list:
    """Exemples sur le systeme JARVIS."""
    examples = []

    examples.append(make_example(
        "Qu'est-ce que JARVIS ?",
        "JARVIS Turbo v10.3 est un assistant IA distribue avec :\n"
        "- 7 agents Claude SDK (ia-deep, ia-fast, ia-check, ia-trading, ia-system, ia-bridge, ia-consensus)\n"
        "- 76 outils MCP pour controler Windows, le cluster, le trading\n"
        "- 84 skills vocales (routine, trading, dev, systeme, productivite)\n"
        "- 1707 commandes vocales groupees en 283 pipelines\n"
        "- Architecture vocale : OpenWakeWord -> Whisper large-v3-turbo CUDA -> TTS Edge fr-FR-HenriNeural\n"
        "- Desktop Electron + React + FastAPI (port 9742)"
    ))

    examples.append(make_example(
        "Comment fonctionne la reconnaissance vocale ?",
        "Pipeline vocal v2 :\n"
        "1. OpenWakeWord detecte 'jarvis' (seuil 0.7)\n"
        "2. Whisper large-v3-turbo transcrit en francais (GPU CUDA)\n"
        "3. Le texte est classifie par le Mode Commandant (classify_task)\n"
        "4. La commande est executee via les skills/tools MCP\n"
        "5. TTS Edge fr-FR-HenriNeural synthetise la reponse\n"
        "Latence : moins de 2 secondes, moins de 0.5s pour les commandes connues (cache LRU 200)."
    ))

    examples.append(make_example(
        "Quelles bases de donnees existent ?",
        "Bases principales :\n"
        "- etoile.db (3.1 MB, 20 tables, ~11000 entries) : map, pipelines, corrections vocales, domino chains, agent keywords, scenarios\n"
        "- jarvis.db (1.5 MB, 11 tables, ~5800 entries) : commandes, skills, scenarios validation, metrics noeuds\n"
        "- trading.db et trading_latest.db : historique de trades et backtest\n"
        "Backups automatiques dans data/backups/."
    ))

    examples.append(make_example(
        "Quels sont les outils MCP ?",
        "76 outils MCP repartis en categories :\n"
        "- LM Studio (11) : query, models, cluster, load/unload, GPU stats, benchmark\n"
        "- Ollama (7) : query, models, pull, web search, subagents, trading\n"
        "- Applications (3) : open_app, close_app, open_url\n"
        "- Fichiers (9) : folder ops, read/write, search\n"
        "- Systeme (8) : info, GPU, reseau, PowerShell, shutdown/restart\n"
        "- Fenetres (4) : list, focus, minimize, maximize\n"
        "- Audio (3) : volume up/down/mute\n"
        "- Et plus : clipboard, clavier, registre, services, notifications."
    ))

    examples.append(make_example(
        "Comment faire un health check ?",
        "Commande : MAO check ou /cluster-check\n"
        "Verifie les 6 noeuds du cluster :\n"
        "- M1 : curl http://127.0.0.1:1234/api/v1/models (sans auth)\n"
        "- M2 : curl http://192.168.1.26:1234/api/v1/models (sans auth)\n"
        "- M3 : curl http://192.168.1.113:1234/api/v1/models (sans auth)\n"
        "- OL1 : curl http://127.0.0.1:11434/api/tags\n"
        "- GEMINI : node gemini-proxy.js --ping\n"
        "- CLAUDE : node claude-proxy.js --ping\n"
        "Timeout 3 secondes par noeud."
    ))

    examples.append(make_example(
        "Comment fonctionne le Mode Commandant ?",
        "Le Mode Commandant (src/commander.py) orchestre les requetes :\n"
        "1. classify_task() : M1 qwen3-30b classe la tache (code/analyse/trading/systeme/web/simple)\n"
        "2. decompose_task() : decoupe en sous-taches si necessaire\n"
        "3. build_commander_enrichment() : construit le contexte pour Claude\n"
        "4. Claude dispatch : execute via les agents SDK\n"
        "Protection thermique : 75C warning, 85C critical -> cascade M1->M2->M3."
    ))

    examples.append(make_example(
        "Quels projets existent ?",
        "12 projets dans F:\\BUREAU :\n"
        "- turbo : MAIN, JARVIS v10.3 SDK\n"
        "- carV1 : Trading AI Ultimate\n"
        "- lienDepart : 14 agents SDK\n"
        "- serveur : Cluster Manager TCP (3 machines)\n"
        "- lm_studio_system : MCP autonome FastAPI port 8000\n"
        "- rag-v1 : RAG adaptatif (plugin LM Studio)\n"
        "- TRADING_V2_PRODUCTION : MCP v3.5\n"
        "- n8n_workflows_backup : 20 workflows\n"
        "Disques : C:\\ (82+ GB libre / 476 GB), F:\\ (104+ GB / 446 GB)."
    ))

    examples.append(make_example(
        "Comment fonctionne le desktop JARVIS ?",
        "JARVIS Desktop (Electron v1.0) :\n"
        "- Stack : Electron 33 + React 19 + Vite 6\n"
        "- Backend : Python FastAPI WebSocket sur port 9742\n"
        "- Pages : Dashboard, Chat, Trading, Voice, Settings\n"
        "- Widgets detachables\n"
        "- System Tray avec raccourci Ctrl+Shift+J\n"
        "- Build : Portable 72.5 MB, NSIS 80 MB\n"
        "- Launcher : launchers/JARVIS.bat"
    ))

    return examples


def generate_trading_examples() -> list:
    """Exemples sur le trading."""
    examples = []

    examples.append(make_example(
        "Quels sont les parametres de trading ?",
        "Configuration MEXC Futures :\n"
        "- Levier : 10x\n"
        "- 10 paires : BTC, ETH, SOL, SUI, PEPE, DOGE, XRP, ADA, AVAX, LINK\n"
        "- Take Profit : 0.4%\n"
        "- Stop Loss : 0.25%\n"
        "- Taille position : 10 USDT\n"
        "- Score minimum : 70/100\n"
        "- DRY_RUN : false (production)"
    ))

    examples.append(make_example(
        "Lance un scan trading",
        "Je lance le pipeline GPU v2.3 :\n"
        "python gpu_pipeline.py --coins 200 --top 10 --json --no-gemini\n"
        "Mode --no-gemini recommande (15-34s au lieu de 65-97s avec Gemini bottleneck). "
        "Le pipeline : data_fetcher -> 100 strategies -> gpu_pipeline -> ai_consensus 5 IA -> dashboard_pro.\n"
        "ATR dynamique : SL = entry - 1.5*ATR, TP1 = entry + 2.25*ATR, TP2 = entry + 4.5*ATR."
    ))

    examples.append(make_example(
        "Comment fonctionne le consensus trading ?",
        "Le consensus trading utilise 6 IA avec vote pondere :\n"
        "- ThreadPoolExecutor par machine (5 groupes), sequentiel intra-machine\n"
        "- Chaque IA recoit les donnees techniques et donne un score\n"
        "- Permission si : consensus >= 60% ET confiance >= 50% ET spread > 20%\n"
        "- Market Regime : trend (>80%), range (60-80%), transition (<60%)\n"
        "- 3 modes : --quick (2 IA, 19s), --no-gemini (5 IA, 15-34s), full (6 IA, 65-97s)"
    ))

    return examples


def generate_skills_examples() -> list:
    """Exemples sur les skills vocales."""
    examples = []

    examples.append(make_example(
        "Quelles routines existent ?",
        "Skills de routine :\n"
        "- rapport_matin : bilan meteo + agenda + marches + cluster status\n"
        "- routine_soir : backup + nettoyage + rapport journee\n"
        "- pause_cafe : musique douce + timer 15min + mode zen\n"
        "- retour_pause : restaure workspace + notifications\n"
        "- rapport_soir : resume activites + performance cluster\n"
        "- fin_journee : sauvegarde tout + shutdown optionnel"
    ))

    examples.append(make_example(
        "Active le mode dev",
        "Mode dev active :\n"
        "- Ouvre VS Code avec le workspace turbo\n"
        "- Lance le terminal avec le bon virtualenv\n"
        "- Affiche le git status\n"
        "- Demarre le dashboard de monitoring\n"
        "- Coupe les notifications non-essentielles\n"
        "Variantes : workspace_frontend, workspace_backend, workspace_turbo, workspace_data, workspace_ml."
    ))

    examples.append(make_example(
        "Fais un diagnostic complet",
        "Diagnostic complet en cours :\n"
        "1. Health check cluster (M1/M2/M3/OL1/GEMINI/CLAUDE)\n"
        "2. GPU : temperatures, VRAM, utilisation\n"
        "3. RAM systeme et espace disque\n"
        "4. Services Windows actifs\n"
        "5. Reseau : ping, DNS, bande passante\n"
        "6. Bases de donnees : integrite + taille\n"
        "Rapport : 10 sections, 6 scores (0-100), Grade A-F. "
        "Dernier audit : Grade A, 82/100."
    ))

    examples.append(make_example(
        "Comment fonctionne le fine-tuning ?",
        "Fine-tuning QLoRA sur Qwen3-8B :\n"
        "- Methode : QLoRA 4-bit NF4 + PEFT LoRA (r=16, alpha=32)\n"
        "- GPU : RTX 3080 seule (CUDA_VISIBLE_DEVICES=5)\n"
        "- Dataset : 17152 exemples (train + eval)\n"
        "- Config : batch=1, grad_accum=8, lr=2e-4, 3 epochs, seq_len=1024\n"
        "- Sauvegarde : checkpoint tous les 50 steps\n"
        "- Patches : Params4bit + QuantState.to pour compatibilite transformers 5.x\n"
        "- Apres training : conversion GGUF pour deploiement dans LM Studio"
    ))

    return examples


def generate_domino_examples_from_db() -> list:
    """Genere des exemples a partir des chaines domino dans etoile.db."""
    examples = []
    db_path = "F:/BUREAU/turbo/data/etoile.db"
    if not os.path.exists(db_path):
        return examples

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Domino chains
    try:
        rows = cur.execute(
            "SELECT trigger_cmd, condition, next_cmd, delay_ms FROM domino_chains LIMIT 30"
        ).fetchall()
        for trigger, condition, next_cmd, delay in rows:
            examples.append(make_example(
                f"Que se passe-t-il apres la commande '{trigger}' ?",
                f"Apres '{trigger}', "
                + (f"si la condition '{condition}' est remplie, " if condition else "")
                + f"la commande suivante '{next_cmd}' se lance"
                + (f" apres un delai de {delay}ms." if delay else " immediatement.")
            ))
    except Exception:
        pass

    # Voice corrections
    try:
        rows = cur.execute(
            "SELECT wrong, correct, category FROM voice_corrections WHERE hit_count > 2 ORDER BY hit_count DESC LIMIT 20"
        ).fetchall()
        for wrong, correct, category in rows:
            examples.append(make_example(
                f"Correction vocale : l'utilisateur dit '{wrong}'",
                f"'{wrong}' est une erreur de reconnaissance vocale. "
                f"La correction est '{correct}'"
                + (f" (categorie : {category})." if category else ".")
            ))
    except Exception:
        pass

    # Pipeline dictionary
    try:
        rows = cur.execute(
            "SELECT trigger_phrase, steps, category FROM pipeline_dictionary LIMIT 20"
        ).fetchall()
        for trigger, steps, category in rows:
            examples.append(make_example(
                f"Que fait le pipeline '{trigger}' ?",
                f"Le pipeline '{trigger}'"
                + (f" (categorie : {category})" if category else "")
                + f" execute les etapes suivantes : {steps}"
            ))
    except Exception:
        pass

    # Scenarios
    try:
        rows = cur.execute(
            "SELECT voice_input, expected_commands, category FROM scenarios LIMIT 20"
        ).fetchall()
        for voice, commands, category in rows[:20]:
            examples.append(make_example(
                voice if voice else "scenario inconnu",
                f"Commandes attendues : {commands}"
                + (f" (categorie : {category})" if category else "")
            ))
    except Exception:
        pass

    conn.close()
    return examples


def generate_commands_from_db() -> list:
    """Genere des exemples a partir des commandes dans jarvis.db."""
    examples = []
    db_path = "F:/BUREAU/turbo/data/jarvis.db"
    if not os.path.exists(db_path):
        return examples

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        rows = cur.execute(
            "SELECT name, description, triggers, category FROM commands WHERE description IS NOT NULL LIMIT 40"
        ).fetchall()
        for name, desc, triggers, category in rows:
            trigger_text = f"Triggers vocaux : {triggers}. " if triggers else ""
            examples.append(make_example(
                f"Explique la commande '{name}'",
                f"{trigger_text}{desc}"
                + (f" Categorie : {category}." if category else "")
            ))
    except Exception:
        pass

    try:
        rows = cur.execute(
            "SELECT name, description, triggers, category FROM skills WHERE description IS NOT NULL LIMIT 20"
        ).fetchall()
        for name, desc, triggers, category in rows:
            trigger_text = f"Triggers vocaux : {triggers}. " if triggers else ""
            examples.append(make_example(
                f"Explique le skill '{name}'",
                f"{trigger_text}{desc}"
                + (f" Categorie : {category}." if category else "")
            ))
    except Exception:
        pass

    conn.close()
    return examples


def main():
    all_examples = []

    print("[1/6] Generation exemples cluster...")
    cluster = generate_cluster_examples()
    all_examples.extend(cluster)
    print(f"  -> {len(cluster)} exemples")

    print("[2/6] Generation exemples systeme...")
    system = generate_system_examples()
    all_examples.extend(system)
    print(f"  -> {len(system)} exemples")

    print("[3/6] Generation exemples trading...")
    trading = generate_trading_examples()
    all_examples.extend(trading)
    print(f"  -> {len(trading)} exemples")

    print("[4/6] Generation exemples skills...")
    skills = generate_skills_examples()
    all_examples.extend(skills)
    print(f"  -> {len(skills)} exemples")

    print("[5/6] Generation exemples domino/corrections (etoile.db)...")
    domino = generate_domino_examples_from_db()
    all_examples.extend(domino)
    print(f"  -> {len(domino)} exemples")

    print("[6/6] Generation exemples commandes/skills (jarvis.db)...")
    commands = generate_commands_from_db()
    all_examples.extend(commands)
    print(f"  -> {len(commands)} exemples")

    # Sauvegarder le fichier enrichissement
    with open(ENRICHMENT_FILE, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"\n[OK] {len(all_examples)} exemples sauves dans {ENRICHMENT_FILE}")

    # Fusionner avec le dataset principal
    existing_count = sum(1 for _ in open(TRAIN_FILE, encoding="utf-8"))
    with open(TRAIN_FILE, "a", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    new_count = existing_count + len(all_examples)
    print(f"[OK] Dataset enrichi : {existing_count} -> {new_count} exemples (+{len(all_examples)})")


if __name__ == "__main__":
    main()
