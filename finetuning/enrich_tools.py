"""
JARVIS Fine-Tuning — Enrichissement Tool Routing
==================================================
Genere des exemples d'entrainement pour apprendre au modele
quel outil MCP appeler pour chaque type de demande utilisateur.

Usage:
    uv run python finetuning/enrich_tools.py
"""

import json
import random
from pathlib import Path

OUTPUT_DIR = Path("F:/BUREAU/turbo/finetuning/dataset")

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

# ========================================================================
# TOOL ROUTING EXAMPLES
# Chaque tool a: name, description, triggers (phrases utilisateur),
# response (reponse JARVIS expliquant l'action)
# ========================================================================

TOOL_EXAMPLES = [
    # === LM STUDIO & IA ===
    {
        "tool": "lm_query",
        "triggers": [
            "demande a l'IA locale",
            "pose cette question a qwen",
            "interroge LM Studio",
            "envoie ca a M1",
            "demande a l'IA d'analyser ca",
            "utilise qwen pour repondre",
        ],
        "response": "J'interroge le modele IA local via LM Studio M1 (qwen3-30b).",
    },
    {
        "tool": "lm_models",
        "triggers": [
            "quels modeles sont charges",
            "liste les modeles LM Studio",
            "montre les modeles sur M1",
            "quels modeles tournent",
        ],
        "response": "Je liste les modeles actuellement charges sur le noeud LM Studio.",
    },
    {
        "tool": "lm_cluster_status",
        "triggers": [
            "status du cluster",
            "etat du cluster IA",
            "comment va le cluster",
            "sante des serveurs IA",
            "verifie les noeuds",
            "status LM Studio et Ollama",
        ],
        "response": "Je verifie la sante de tous les noeuds du cluster (LM Studio M1, M2, Ollama).",
    },
    {
        "tool": "consensus",
        "triggers": [
            "consensus multi-IA",
            "demande a plusieurs IA",
            "consensus sur cette question",
            "avis de toutes les IA",
            "fais un consensus",
        ],
        "response": "Je lance un consensus multi-noeuds : plusieurs IA analysent la question en parallele.",
    },
    {
        "tool": "lm_load_model",
        "triggers": [
            "charge le modele",
            "load qwen sur M1",
            "charge un nouveau modele",
            "mets ce modele en memoire",
            "installe le modele sur le GPU",
        ],
        "response": "Je charge le modele demande sur M1 via LM Studio CLI.",
    },
    {
        "tool": "lm_unload_model",
        "triggers": [
            "decharge le modele",
            "libere la VRAM",
            "enleve ce modele",
            "unload le modele",
            "retire le modele de la memoire",
        ],
        "response": "Je decharge le modele de la VRAM pour liberer de l'espace GPU.",
    },
    {
        "tool": "lm_switch_coder",
        "triggers": [
            "passe en mode code",
            "charge le modele de code",
            "switch vers le coder",
            "je veux coder",
            "mode developpement",
        ],
        "response": "Je bascule M1 en mode code : chargement de qwen3-coder-30b.",
    },
    {
        "tool": "lm_switch_dev",
        "triggers": [
            "charge devstral",
            "passe en mode devstral",
            "switch vers devstral",
        ],
        "response": "Je bascule M1 en mode dev : chargement de devstral.",
    },
    {
        "tool": "lm_gpu_stats",
        "triggers": [
            "stats GPU",
            "utilisation GPU",
            "VRAM utilisee",
            "temperature des GPU",
            "combien de VRAM libre",
            "etat des cartes graphiques",
        ],
        "response": "J'affiche les statistiques GPU detaillees : VRAM, utilisation, temperature.",
    },
    {
        "tool": "lm_benchmark",
        "triggers": [
            "benchmark le cluster",
            "teste la latence des serveurs",
            "mesure la vitesse des noeuds",
            "benchmark M1 M2",
        ],
        "response": "Je lance un benchmark de latence sur les noeuds M1, M2 et Ollama.",
    },
    {
        "tool": "lm_perf_metrics",
        "triggers": [
            "metriques de performance",
            "latences moyennes",
            "stats de performance du cluster",
            "combien de requetes traitees",
        ],
        "response": "J'affiche les metriques de performance du cluster : latences, requetes.",
    },

    # === OLLAMA ===
    {
        "tool": "ollama_query",
        "triggers": [
            "demande a Ollama",
            "interroge qwen 1.7b",
            "utilise Ollama pour ca",
            "question rapide a l'IA",
        ],
        "response": "J'interroge Ollama (modele local qwen3:1.7b).",
    },
    {
        "tool": "ollama_models",
        "triggers": [
            "modeles Ollama disponibles",
            "liste les modeles Ollama",
            "quels modeles cloud",
        ],
        "response": "Je liste les modeles Ollama disponibles (locaux et cloud).",
    },
    {
        "tool": "ollama_pull",
        "triggers": [
            "telecharge ce modele Ollama",
            "pull un modele",
            "installe un modele Ollama",
        ],
        "response": "Je telecharge le modele demande via Ollama.",
    },
    {
        "tool": "ollama_status",
        "triggers": [
            "status Ollama",
            "etat d'Ollama",
            "Ollama fonctionne",
        ],
        "response": "Je verifie la sante du backend Ollama : version, modeles, status.",
    },
    {
        "tool": "ollama_web_search",
        "triggers": [
            "cherche sur internet",
            "recherche web",
            "trouve des infos sur",
            "google ca",
            "qu'est-ce que dit internet sur",
            "fais une recherche en ligne",
        ],
        "response": "Je lance une recherche web via Ollama cloud (minimax-m2.5).",
    },
    {
        "tool": "ollama_subagents",
        "triggers": [
            "lance les sous-agents",
            "analyse avec 3 IA cloud",
            "multi-agents sur ce sujet",
            "fais analyser par les sous-agents",
        ],
        "response": "Je lance 3 sous-agents Ollama cloud en parallele pour analyser le sujet.",
    },
    {
        "tool": "ollama_trading_analysis",
        "triggers": [
            "analyse trading via sous-agents",
            "trading analysis cloud",
            "analyse BTC par les sous-agents",
        ],
        "response": "Je lance une analyse trading parallele via 3 sous-agents cloud.",
    },

    # === SCRIPTS & PROJETS ===
    {
        "tool": "run_script",
        "triggers": [
            "lance le script",
            "execute le script Python",
            "run le scanner",
            "lance le pipeline trading",
            "execute le backtest",
        ],
        "response": "J'execute le script Python demande.",
    },
    {
        "tool": "list_scripts",
        "triggers": [
            "quels scripts sont disponibles",
            "liste les scripts",
            "montre les scripts Python",
        ],
        "response": "Je liste les scripts Python disponibles et indexes.",
    },
    {
        "tool": "list_project_paths",
        "triggers": [
            "quels projets existent",
            "liste les dossiers projets",
            "ou sont les projets",
        ],
        "response": "Je liste les dossiers projets indexes dans la configuration.",
    },

    # === APPLICATIONS ===
    {
        "tool": "open_app",
        "triggers": [
            "ouvre Chrome",
            "lance VSCode",
            "ouvre Discord",
            "demarre Spotify",
            "ouvre le terminal",
            "lance LM Studio",
            "ouvre le gestionnaire de taches",
            "lance OBS",
            "ouvre Paint",
        ],
        "response": "J'ouvre l'application demandee.",
    },
    {
        "tool": "close_app",
        "triggers": [
            "ferme Chrome",
            "quitte VSCode",
            "ferme Discord",
            "arrete Spotify",
        ],
        "response": "Je ferme l'application demandee.",
    },
    {
        "tool": "open_url_tool",
        "triggers": [
            "ouvre ce site",
            "va sur YouTube",
            "ouvre Gmail",
            "ouvre TradingView",
            "va sur MEXC",
            "ouvre GitHub",
        ],
        "response": "J'ouvre l'URL dans le navigateur.",
    },

    # === PROCESSUS ===
    {
        "tool": "list_processes_tool",
        "triggers": [
            "liste les processus",
            "quels processus tournent",
            "montre les processus Windows",
            "qu'est-ce qui tourne en arriere-plan",
        ],
        "response": "Je liste les processus Windows en cours d'execution.",
    },
    {
        "tool": "kill_process_tool",
        "triggers": [
            "tue ce processus",
            "arrete ce programme",
            "kill le processus",
            "force la fermeture",
        ],
        "response": "J'arrete le processus demande.",
    },

    # === FENETRES ===
    {
        "tool": "list_windows_tool",
        "triggers": [
            "liste les fenetres ouvertes",
            "quelles fenetres sont ouvertes",
            "montre les fenetres",
        ],
        "response": "Je liste toutes les fenetres visibles avec leurs titres.",
    },
    {
        "tool": "focus_window_tool",
        "triggers": [
            "mets Chrome devant",
            "focus sur VSCode",
            "passe sur cette fenetre",
            "ramene cette fenetre",
        ],
        "response": "Je mets la fenetre demandee au premier plan.",
    },
    {
        "tool": "minimize_window_tool",
        "triggers": [
            "minimise la fenetre",
            "reduis la fenetre",
            "mets en arriere-plan",
        ],
        "response": "Je minimise la fenetre demandee.",
    },
    {
        "tool": "maximize_window_tool",
        "triggers": [
            "maximise la fenetre",
            "plein ecran",
            "agrandis la fenetre",
        ],
        "response": "Je maximise la fenetre demandee.",
    },

    # === CLAVIER & SOURIS ===
    {
        "tool": "send_keys_tool",
        "triggers": [
            "envoie les touches",
            "appuie sur entree",
            "tape echap",
        ],
        "response": "J'envoie les touches clavier a la fenetre active.",
    },
    {
        "tool": "type_text_tool",
        "triggers": [
            "tape ce texte",
            "ecris dans le champ",
            "saisis ce message",
            "entre ce texte",
        ],
        "response": "Je tape le texte dans la fenetre active.",
    },
    {
        "tool": "press_hotkey_tool",
        "triggers": [
            "fais ctrl+c",
            "copie ca",
            "ctrl+v pour coller",
            "alt+tab",
            "ctrl+z pour annuler",
            "ctrl+s pour sauvegarder",
        ],
        "response": "J'envoie le raccourci clavier demande.",
    },
    {
        "tool": "mouse_click_tool",
        "triggers": [
            "clique ici",
            "clique a cette position",
            "clic souris",
        ],
        "response": "Je clique aux coordonnees indiquees.",
    },

    # === PRESSE-PAPIER ===
    {
        "tool": "clipboard_get_tool",
        "triggers": [
            "qu'est-ce qu'il y a dans le presse-papier",
            "lis le presse-papier",
            "montre le clipboard",
            "contenu du presse-papier",
        ],
        "response": "Je lis le contenu actuel du presse-papier.",
    },
    {
        "tool": "clipboard_set_tool",
        "triggers": [
            "copie ca dans le presse-papier",
            "mets ce texte dans le clipboard",
            "copie cette valeur",
        ],
        "response": "J'ecris le texte dans le presse-papier.",
    },

    # === FICHIERS ===
    {
        "tool": "open_folder_tool",
        "triggers": [
            "ouvre le dossier",
            "ouvre l'explorateur",
            "montre le dossier Bureau",
            "ouvre Documents",
        ],
        "response": "J'ouvre le dossier dans l'Explorateur Windows.",
    },
    {
        "tool": "list_folder_tool",
        "triggers": [
            "liste les fichiers",
            "qu'est-ce qu'il y a dans ce dossier",
            "contenu du dossier",
            "montre les fichiers du projet",
        ],
        "response": "Je liste le contenu du dossier demande.",
    },
    {
        "tool": "create_folder_tool",
        "triggers": [
            "cree un dossier",
            "nouveau dossier",
            "mkdir",
        ],
        "response": "Je cree le nouveau dossier.",
    },
    {
        "tool": "copy_item_tool",
        "triggers": [
            "copie ce fichier",
            "duplique le fichier",
            "copie vers",
        ],
        "response": "Je copie le fichier ou dossier vers la destination.",
    },
    {
        "tool": "move_item_tool",
        "triggers": [
            "deplace ce fichier",
            "bouge le fichier vers",
            "transfere le dossier",
        ],
        "response": "Je deplace le fichier ou dossier vers la destination.",
    },
    {
        "tool": "delete_item_tool",
        "triggers": [
            "supprime ce fichier",
            "efface le fichier",
            "mets a la corbeille",
        ],
        "response": "Je supprime le fichier (vers la corbeille).",
    },
    {
        "tool": "read_text_file_tool",
        "triggers": [
            "lis ce fichier",
            "montre le contenu du fichier",
            "affiche le fichier",
            "ouvre et lis le fichier texte",
        ],
        "response": "Je lis le contenu du fichier texte.",
    },
    {
        "tool": "write_text_file_tool",
        "triggers": [
            "ecris dans ce fichier",
            "sauvegarde dans le fichier",
            "cree un fichier avec ce contenu",
        ],
        "response": "J'ecris le contenu dans le fichier texte.",
    },
    {
        "tool": "search_files_tool",
        "triggers": [
            "cherche des fichiers",
            "trouve les fichiers Python",
            "recherche les fichiers qui contiennent",
            "ou est ce fichier",
        ],
        "response": "Je cherche les fichiers correspondants recursivement.",
    },

    # === AUDIO ===
    {
        "tool": "volume_up_tool",
        "triggers": [
            "monte le son",
            "augmente le volume",
            "plus fort",
        ],
        "response": "J'augmente le volume systeme.",
    },
    {
        "tool": "volume_down_tool",
        "triggers": [
            "baisse le son",
            "diminue le volume",
            "moins fort",
        ],
        "response": "Je baisse le volume systeme.",
    },
    {
        "tool": "volume_mute_tool",
        "triggers": [
            "mute",
            "coupe le son",
            "silence",
            "remets le son",
        ],
        "response": "Je bascule le mode muet.",
    },

    # === ECRAN ===
    {
        "tool": "screenshot_tool",
        "triggers": [
            "prends une capture d'ecran",
            "screenshot",
            "capture l'ecran",
            "fais un screen",
        ],
        "response": "Je prends une capture d'ecran.",
    },
    {
        "tool": "screen_resolution_tool",
        "triggers": [
            "quelle est la resolution",
            "resolution de l'ecran",
            "taille de l'ecran",
        ],
        "response": "J'affiche la resolution actuelle de l'ecran.",
    },

    # === SYSTEME ===
    {
        "tool": "system_info_tool",
        "triggers": [
            "infos systeme",
            "etat du systeme",
            "CPU et RAM",
            "combien de RAM disponible",
            "uptime du PC",
            "informations de l'ordinateur",
        ],
        "response": "J'affiche les informations systeme completes : CPU, RAM, GPU, disques, uptime.",
    },
    {
        "tool": "gpu_info_tool",
        "triggers": [
            "infos GPU detaillees",
            "quel driver NVIDIA",
            "version du driver GPU",
        ],
        "response": "J'affiche les informations detaillees des GPU (VRAM, driver).",
    },
    {
        "tool": "network_info_tool",
        "triggers": [
            "quelle est mon IP",
            "adresse IP locale",
            "interfaces reseau",
            "infos reseau",
        ],
        "response": "J'affiche les adresses IP et les interfaces reseau.",
    },
    {
        "tool": "powershell_run_tool",
        "triggers": [
            "execute cette commande PowerShell",
            "lance une commande systeme",
            "run cette commande",
            "execute en PowerShell",
        ],
        "response": "J'execute la commande PowerShell demandee.",
    },
    {
        "tool": "lock_screen_tool",
        "triggers": [
            "verrouille le PC",
            "lock l'ecran",
            "verrouille la session",
        ],
        "response": "Je verrouille le PC.",
    },
    {
        "tool": "shutdown_pc_tool",
        "triggers": [
            "eteins le PC",
            "arrete l'ordinateur",
            "shutdown",
        ],
        "response": "J'eteins le PC. Confirmation necessaire.",
    },
    {
        "tool": "restart_pc_tool",
        "triggers": [
            "redemarre le PC",
            "reboot",
            "restart l'ordinateur",
        ],
        "response": "Je redemarre le PC. Confirmation necessaire.",
    },
    {
        "tool": "sleep_pc_tool",
        "triggers": [
            "mets en veille",
            "sleep le PC",
            "mode veille",
        ],
        "response": "Je mets le PC en veille.",
    },

    # === SERVICES ===
    {
        "tool": "list_services_tool",
        "triggers": [
            "liste les services",
            "quels services tournent",
            "services Windows actifs",
        ],
        "response": "Je liste les services Windows.",
    },
    {
        "tool": "start_service_tool",
        "triggers": [
            "demarre le service",
            "lance le service",
            "active le service",
        ],
        "response": "Je demarre le service Windows demande.",
    },
    {
        "tool": "stop_service_tool",
        "triggers": [
            "arrete le service",
            "stoppe le service",
            "desactive le service",
        ],
        "response": "J'arrete le service Windows demande.",
    },

    # === RESEAU ===
    {
        "tool": "wifi_networks_tool",
        "triggers": [
            "quels reseaux WiFi",
            "liste les WiFi disponibles",
            "reseaux sans fil",
        ],
        "response": "Je liste les reseaux WiFi disponibles.",
    },
    {
        "tool": "ping_tool",
        "triggers": [
            "ping Google",
            "teste la connexion",
            "ping ce serveur",
            "verifie si le serveur repond",
        ],
        "response": "Je ping l'hote pour verifier la connectivite.",
    },
    {
        "tool": "get_ip_tool",
        "triggers": [
            "mon adresse IP",
            "quelle est mon IP",
            "IP locale",
        ],
        "response": "J'affiche les adresses IP locales.",
    },

    # === REGISTRE ===
    {
        "tool": "registry_read_tool",
        "triggers": [
            "lis la cle de registre",
            "valeur du registre",
            "verifie dans le registre",
        ],
        "response": "Je lis la valeur dans le registre Windows.",
    },
    {
        "tool": "registry_write_tool",
        "triggers": [
            "ecris dans le registre",
            "modifie la cle de registre",
            "change cette valeur du registre",
        ],
        "response": "J'ecris la valeur dans le registre Windows. Attention : operation sensible.",
    },

    # === NOTIFICATIONS & VOIX ===
    {
        "tool": "notify_tool",
        "triggers": [
            "envoie une notification",
            "affiche un toast",
            "notifie-moi",
            "alerte Windows",
        ],
        "response": "J'envoie une notification toast Windows.",
    },
    {
        "tool": "speak_tool",
        "triggers": [
            "dis ca a voix haute",
            "parle",
            "lis ce texte a voix haute",
            "synthese vocale",
        ],
        "response": "Je lis le texte a voix haute via la synthese vocale Windows.",
    },
    {
        "tool": "scheduled_tasks_tool",
        "triggers": [
            "taches planifiees",
            "liste les taches Windows",
            "quelles taches sont programmees",
        ],
        "response": "Je liste les taches planifiees Windows.",
    },
]


def generate_conversations() -> list[dict]:
    """Genere les conversations de tool routing."""
    convs = []

    for example in TOOL_EXAMPLES:
        tool_name = example["tool"]
        response = example["response"]

        for trigger in example["triggers"]:
            # Version directe : phrase -> action
            convs.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": trigger},
                    {"role": "assistant", "content": response},
                ]
            })

            # Version avec contexte tool call
            tool_response = (
                f"{response}\n\n"
                f"[Outil utilise : {tool_name}]"
            )
            convs.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": trigger},
                    {"role": "assistant", "content": tool_response},
                ]
            })

    return convs


def enrich_dataset(convs: list[dict]):
    """Ajoute les conversations de tool routing au dataset existant."""
    train_path = OUTPUT_DIR / "jarvis_finetune_train.jsonl"
    eval_path = OUTPUT_DIR / "jarvis_finetune_eval.jsonl"

    if not train_path.exists():
        print("[ERREUR] Dataset train non trouve ! Lancez prepare_dataset.py d'abord.")
        return

    # Lire le dataset existant
    with open(train_path, "r", encoding="utf-8") as f:
        existing_train = [json.loads(l) for l in f]

    with open(eval_path, "r", encoding="utf-8") as f:
        existing_eval = [json.loads(l) for l in f]

    # Split tool routing 95/5
    random.seed(42)
    random.shuffle(convs)
    split = int(len(convs) * 0.95)
    tool_train = convs[:split]
    tool_eval = convs[split:]

    # Fusionner
    all_train = existing_train + tool_train
    all_eval = existing_eval + tool_eval

    # Re-shuffle
    random.shuffle(all_train)
    random.shuffle(all_eval)

    # Sauvegarder
    for data, path in [(all_train, train_path), (all_eval, eval_path)]:
        with open(path, "w", encoding="utf-8") as f:
            for conv in data:
                f.write(json.dumps(conv, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"Dataset enrichi avec tool routing !")
    print(f"  Tools: {len(TOOL_EXAMPLES)} outils, {len(convs)} exemples generes")
    print(f"  Train : {len(all_train)} exemples (avant: {len(existing_train)})")
    print(f"  Eval  : {len(all_eval)} exemples (avant: {len(existing_eval)})")
    print(f"  Ajout : +{len(convs)} exemples de tool routing")
    print(f"{'='*60}")


def main():
    print("=" * 60)
    print("JARVIS Fine-Tuning — Enrichissement Tool Routing")
    print("=" * 60)

    convs = generate_conversations()
    print(f"\n[OK] {len(convs)} exemples de tool routing generes")
    print(f"     ({len(TOOL_EXAMPLES)} outils, ~{len(convs)//len(TOOL_EXAMPLES)} variantes/outil)")

    enrich_dataset(convs)


if __name__ == "__main__":
    main()
