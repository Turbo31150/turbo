"""
JARVIS Fine-Tuning — Enrichissement MCP Tools externes
========================================================
Ajoute les outils MCP externes (trading, n8n, Telegram, SQL,
filesystem, LM Studio servers, etc.) au dataset.

Usage:
    uv run python finetuning/enrich_mcp_tools.py
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

MCP_TOOL_EXAMPLES = [
    # ═══════════════════════════════════════════════════════════
    # LM STUDIO MCP SERVERS
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "lmstudio1_chat",
        "triggers": [
            "parle a M1", "envoie a LM Studio M1", "chat avec M1",
            "demande a M1", "question pour M1",
        ],
        "response": "J'envoie la requete au serveur LM Studio M1 (10.5.0.2:1234).",
    },
    {
        "tool": "lmstudio1_models",
        "triggers": [
            "modeles sur M1", "quels modeles sur le serveur principal",
            "liste modeles M1",
        ],
        "response": "Je liste les modeles charges sur le serveur LM Studio M1.",
    },
    {
        "tool": "lmstudio1_status",
        "triggers": [
            "status M1", "M1 est en ligne", "etat de M1",
            "serveur principal fonctionne",
        ],
        "response": "Je verifie le status du serveur LM Studio M1.",
    },
    {
        "tool": "lmstudio2_chat",
        "triggers": [
            "parle a M2", "envoie a M2", "chat avec M2",
            "demande a deepseek",
        ],
        "response": "J'envoie la requete au serveur LM Studio M2 (192.168.1.26:1234).",
    },
    {
        "tool": "lmstudio2_models",
        "triggers": [
            "modeles sur M2", "quels modeles sur le serveur secondaire",
        ],
        "response": "Je liste les modeles charges sur le serveur LM Studio M2.",
    },
    {
        "tool": "lmstudio2_status",
        "triggers": [
            "status M2", "M2 fonctionne", "etat de M2",
        ],
        "response": "Je verifie le status du serveur LM Studio M2.",
    },

    # ═══════════════════════════════════════════════════════════
    # BROWSER & JAVASCRIPT
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "run_javascript",
        "triggers": [
            "execute du JavaScript", "lance ce code JS",
            "run ce JavaScript dans le navigateur",
        ],
        "response": "J'execute le code JavaScript.",
    },

    # ═══════════════════════════════════════════════════════════
    # FILESYSTEM MCP
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "read_file",
        "triggers": [
            "lis ce fichier", "ouvre ce fichier", "affiche le contenu",
            "montre moi le fichier",
        ],
        "response": "Je lis le fichier demande.",
    },
    {
        "tool": "read_multiple_files",
        "triggers": [
            "lis plusieurs fichiers", "ouvre ces fichiers",
            "montre moi ces fichiers en meme temps",
        ],
        "response": "Je lis plusieurs fichiers simultanement.",
    },
    {
        "tool": "write_file",
        "triggers": [
            "ecris ce fichier", "cree un fichier", "sauvegarde dans un fichier",
        ],
        "response": "J'ecris le contenu dans le fichier.",
    },
    {
        "tool": "edit_file",
        "triggers": [
            "modifie ce fichier", "edite le fichier", "change cette ligne",
        ],
        "response": "Je modifie le fichier demande.",
    },
    {
        "tool": "directory_tree",
        "triggers": [
            "arbre du dossier", "structure du projet", "tree du repertoire",
            "montre l'arborescence",
        ],
        "response": "J'affiche l'arborescence du dossier.",
    },
    {
        "tool": "search_files",
        "triggers": [
            "cherche un fichier", "trouve ce fichier", "ou est ce fichier",
        ],
        "response": "Je recherche les fichiers correspondants.",
    },
    {
        "tool": "get_file_info",
        "triggers": [
            "infos sur ce fichier", "taille du fichier", "date du fichier",
        ],
        "response": "J'affiche les informations du fichier.",
    },
    {
        "tool": "list_directory_with_sizes",
        "triggers": [
            "taille des fichiers du dossier", "espace occupe dans ce dossier",
        ],
        "response": "Je liste le contenu du dossier avec les tailles.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — SCANNING
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "scan_mexc",
        "triggers": [
            "scanne MEXC", "scan le marche", "analyse les paires MEXC",
            "quelles paires bougent", "scan les crypto",
        ],
        "response": "Je scanne les paires sur MEXC Futures pour detecter les opportunites.",
    },
    {
        "tool": "scan_sniper",
        "triggers": [
            "lance le sniper", "scan sniper", "mode sniper MEXC",
            "cherche les entrees sniper",
        ],
        "response": "Je lance le scan sniper pour detecter les entrees precises.",
    },
    {
        "tool": "detect_pumps",
        "triggers": [
            "detecte les pumps", "quelles crypto pumpent",
            "y a des pumps en cours", "mouvements anormaux",
        ],
        "response": "Je scanne MEXC pour detecter les mouvements de pump en cours.",
    },
    {
        "tool": "detect_imminent_pumps",
        "triggers": [
            "pumps imminents", "quelles crypto vont pumper",
            "detecte les pumps a venir", "signaux pre-pump",
        ],
        "response": "Je detecte les pumps imminents sur MEXC Futures.",
    },
    {
        "tool": "smart_scan",
        "triggers": [
            "scan intelligent", "smart scan MEXC", "analyse intelligente du marche",
            "scan complet du marche",
        ],
        "response": "Je lance un scan intelligent multi-criteres du marche MEXC.",
    },
    {
        "tool": "scan_all_pumps",
        "triggers": [
            "scan tous les pumps", "detecte tous les mouvements",
            "rapport complet des pumps",
        ],
        "response": "Je scanne tous les pumps en cours sur MEXC.",
    },
    {
        "tool": "scan_best_opportunities",
        "triggers": [
            "meilleures opportunites", "quelles sont les meilleures paires",
            "opportunites trading", "top signaux",
        ],
        "response": "Je scanne les meilleures opportunites de trading sur MEXC.",
    },
    {
        "tool": "scan_breakout_imminent",
        "triggers": [
            "breakout imminent", "quelles paires vont casser",
            "detecte les breakouts", "cassure de range",
        ],
        "response": "Je detecte les breakouts imminents sur MEXC Futures.",
    },
    {
        "tool": "multi_scanner_pipeline",
        "triggers": [
            "lance le multi-scanner", "pipeline de scan complet",
            "scan tous les detecteurs",
        ],
        "response": "Je lance le pipeline multi-scanner complet.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — POSITIONS & MARGIN
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "get_mexc_positions",
        "triggers": [
            "mes positions MEXC", "positions ouvertes", "quelles positions",
            "montre mes trades actifs",
        ],
        "response": "J'affiche les positions ouvertes sur MEXC Futures.",
    },
    {
        "tool": "get_margin_ratios",
        "triggers": [
            "ratios de marge", "marge disponible", "ratio de risque",
        ],
        "response": "J'affiche les ratios de marge de tes positions.",
    },
    {
        "tool": "check_critical_margins",
        "triggers": [
            "marges critiques", "positions en danger", "risque de liquidation",
            "check la marge",
        ],
        "response": "Je verifie les marges critiques pour detecter les risques de liquidation.",
    },
    {
        "tool": "suggest_margin_transfer",
        "triggers": [
            "transfert de marge", "reequilibre la marge",
            "suggestion transfert marge",
        ],
        "response": "J'analyse et suggere des transferts de marge pour equilibrer les positions.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — ANALYSIS
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "deep_analyze_coin",
        "triggers": [
            "analyse approfondie BTC", "analyse en profondeur ETH",
            "analyse complete cette crypto", "deep analyse",
        ],
        "response": "Je lance une analyse approfondie de la crypto demandee.",
    },
    {
        "tool": "analyze_coin_deep",
        "triggers": [
            "analyse detaillee", "analyse technique complete",
            "etudie cette paire en detail",
        ],
        "response": "J'analyse la paire en profondeur avec tous les indicateurs.",
    },
    {
        "tool": "validate_direction",
        "triggers": [
            "valide la direction", "c'est long ou short",
            "confirme le signal", "direction de cette paire",
        ],
        "response": "Je valide la direction (long/short) pour la paire demandee.",
    },
    {
        "tool": "batch_validate_directions",
        "triggers": [
            "valide toutes les directions", "confirme tous les signaux",
            "validation en batch",
        ],
        "response": "Je valide les directions pour toutes les paires en batch.",
    },
    {
        "tool": "quick_validate_direction",
        "triggers": [
            "validation rapide", "direction rapide", "quick check direction",
        ],
        "response": "Je valide rapidement la direction de la paire.",
    },
    {
        "tool": "multi_coin_analysis",
        "triggers": [
            "analyse multi-coins", "compare ces cryptos",
            "analyse plusieurs paires",
        ],
        "response": "J'analyse plusieurs cryptos simultanement pour comparaison.",
    },
    {
        "tool": "calculate_indicators_only",
        "triggers": [
            "calcule les indicateurs", "RSI et MACD", "indicateurs techniques",
        ],
        "response": "Je calcule les indicateurs techniques pour la paire demandee.",
    },
    {
        "tool": "calculate_entry_tp_sl",
        "triggers": [
            "calcule entree TP SL", "niveaux d'entree", "ou mettre le stop loss",
            "calcule le take profit",
        ],
        "response": "Je calcule les niveaux d'entree, Take Profit et Stop Loss.",
    },
    {
        "tool": "get_ohlcv_ccxt",
        "triggers": [
            "donnees OHLCV", "bougies de cette paire", "historique des prix",
            "candlesticks", "prix historiques",
        ],
        "response": "Je recupere les donnees OHLCV (bougies) via CCXT.",
    },
    {
        "tool": "get_orderbook_analysis",
        "triggers": [
            "analyse le carnet d'ordres", "orderbook", "profondeur du marche",
            "ordres d'achat et vente",
        ],
        "response": "J'analyse le carnet d'ordres pour la paire demandee.",
    },
    {
        "tool": "get_onchain_flow",
        "triggers": [
            "flux on-chain", "mouvements de whales", "analyse on-chain",
        ],
        "response": "J'analyse les flux on-chain pour detecter les mouvements de whales.",
    },
    {
        "tool": "get_breakout_score_enhanced",
        "triggers": [
            "score de breakout", "potentiel de cassure", "breakout score",
        ],
        "response": "Je calcule le score de breakout ameliore pour la paire.",
    },
    {
        "tool": "get_multi_timeframe_data",
        "triggers": [
            "donnees multi-timeframe", "analyse multi-TF",
            "compare les timeframes",
        ],
        "response": "Je recupere les donnees sur plusieurs timeframes.",
    },
    {
        "tool": "direction_validator_status",
        "triggers": [
            "status du validateur", "etat du direction validator",
        ],
        "response": "J'affiche le status du validateur de direction.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — CONSENSUS & ROUTING IA
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "turbo_consensus",
        "triggers": [
            "consensus turbo", "avis de toutes les IA sur cette paire",
            "consensus trading", "que disent les IA",
        ],
        "response": "Je lance un consensus turbo multi-IA pour analyser la paire.",
    },
    {
        "tool": "turbo_scan",
        "triggers": [
            "scan turbo", "scan rapide du marche", "turbo scan MEXC",
        ],
        "response": "Je lance un scan turbo rapide du marche MEXC.",
    },
    {
        "tool": "parallel_consensus",
        "triggers": [
            "consensus parallele", "toutes les IA en parallele",
            "consensus multi-serveurs",
        ],
        "response": "Je lance un consensus en parallele sur tous les serveurs IA.",
    },
    {
        "tool": "get_multi_ia_consensus",
        "triggers": [
            "resultat du consensus", "avis multi-IA",
            "qu'ont dit les IA",
        ],
        "response": "J'affiche le resultat du consensus multi-IA.",
    },
    {
        "tool": "smart_route",
        "triggers": [
            "route intelligemment", "envoie au meilleur serveur",
            "routage intelligent",
        ],
        "response": "J'utilise le routage intelligent pour envoyer au serveur optimal.",
    },
    {
        "tool": "build_trading_context",
        "triggers": [
            "construis le contexte trading", "contexte de marche",
            "resume la situation du marche",
        ],
        "response": "Je construis le contexte trading complet pour l'analyse.",
    },
    {
        "tool": "update_consensus_outcome",
        "triggers": [
            "mets a jour le resultat du consensus",
            "feedback sur le consensus", "resultat du trade",
        ],
        "response": "Je mets a jour le resultat du consensus avec le feedback reel.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — EXECUTION & MONITORING
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "run_trading_v4",
        "triggers": [
            "lance le trading V4", "demarre le bot trading",
            "active le trading automatique",
        ],
        "response": "Je lance le systeme de trading V4.",
    },
    {
        "tool": "run_scanner_pro",
        "triggers": [
            "lance le scanner pro", "scanner professionnel",
            "scan avance du marche",
        ],
        "response": "Je lance le scanner professionnel.",
    },
    {
        "tool": "run_backtest",
        "triggers": [
            "lance un backtest", "teste la strategie", "backtest cette config",
            "simule le trading",
        ],
        "response": "Je lance un backtest de la strategie de trading.",
    },
    {
        "tool": "start_realtime_monitor",
        "triggers": [
            "demarre le monitoring", "surveillance en temps reel",
            "active le monitor live",
        ],
        "response": "Je demarre la surveillance en temps reel du marche.",
    },
    {
        "tool": "stop_realtime_monitor",
        "triggers": [
            "arrete le monitoring", "stop la surveillance",
            "desactive le monitor",
        ],
        "response": "J'arrete la surveillance en temps reel.",
    },
    {
        "tool": "get_live_dashboard",
        "triggers": [
            "dashboard live", "tableau de bord trading",
            "montre le dashboard en direct",
        ],
        "response": "J'affiche le dashboard de trading en direct.",
    },
    {
        "tool": "live_mode",
        "triggers": [
            "mode live", "trading en direct", "passe en mode live",
        ],
        "response": "J'active le mode trading en direct.",
    },
    {
        "tool": "get_trade_history",
        "triggers": [
            "historique des trades", "mes anciens trades",
            "montre l'historique trading",
        ],
        "response": "J'affiche l'historique des trades.",
    },
    {
        "tool": "add_trade",
        "triggers": [
            "ajoute un trade", "enregistre ce trade", "log ce trade",
        ],
        "response": "J'enregistre le trade dans l'historique.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — PUMP DETECTOR
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "pump_detector_scan",
        "triggers": [
            "scan pump detector", "detecteur de pump scan",
            "analyse les pumps en detail",
        ],
        "response": "Je lance le detecteur de pumps pour scanner le marche.",
    },
    {
        "tool": "pump_detector_live",
        "triggers": [
            "pump detector live", "detecteur de pump en direct",
            "surveille les pumps en continu",
        ],
        "response": "J'active le detecteur de pumps en mode live.",
    },

    # ═══════════════════════════════════════════════════════════
    # TRADING — WHALE HUNTER
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "wh_scan_market",
        "triggers": [
            "whale hunter scan", "scan whale", "detecte les whales",
            "mouvements de gros porteurs",
        ],
        "response": "Je scanne le marche avec le Whale Hunter.",
    },
    {
        "tool": "wh_multi_ia_consensus",
        "triggers": [
            "consensus whale hunter", "avis IA whale",
        ],
        "response": "Je lance un consensus multi-IA via le Whale Hunter.",
    },
    {
        "tool": "wh_analyze_coin",
        "triggers": [
            "whale analysis", "analyse whale de cette paire",
        ],
        "response": "J'analyse la paire avec le module Whale Hunter.",
    },
    {
        "tool": "wh_fvg_scanner",
        "triggers": [
            "scan FVG", "fair value gaps", "detecte les FVG",
            "zones de desequilibre",
        ],
        "response": "Je scanne les Fair Value Gaps (FVG) sur le marche.",
    },
    {
        "tool": "wh_send_telegram",
        "triggers": [
            "envoie alerte whale Telegram", "telegram whale hunter",
        ],
        "response": "J'envoie une alerte Whale Hunter via Telegram.",
    },
    {
        "tool": "wh_get_status",
        "triggers": [
            "status whale hunter", "etat du whale hunter",
        ],
        "response": "J'affiche le status du module Whale Hunter.",
    },
    {
        "tool": "wh_trading_signal",
        "triggers": [
            "signal whale hunter", "signal de trading whale",
        ],
        "response": "Je genere un signal de trading via le Whale Hunter.",
    },

    # ═══════════════════════════════════════════════════════════
    # TELEGRAM & ALERTES
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "send_telegram",
        "triggers": [
            "envoie sur Telegram", "message Telegram", "envoie un message",
        ],
        "response": "J'envoie le message via Telegram.",
    },
    {
        "tool": "send_telegram_alert",
        "triggers": [
            "alerte Telegram", "envoie une alerte", "notification Telegram",
        ],
        "response": "J'envoie une alerte via Telegram.",
    },
    {
        "tool": "set_price_alert",
        "triggers": [
            "alerte de prix", "previens moi si BTC atteint",
            "alerte quand le prix monte", "set price alert",
        ],
        "response": "Je configure une alerte de prix.",
    },
    {
        "tool": "set_margin_alert",
        "triggers": [
            "alerte de marge", "previens si la marge descend",
        ],
        "response": "Je configure une alerte de marge.",
    },
    {
        "tool": "check_all_alerts",
        "triggers": [
            "verifie les alertes", "check les alertes actives",
        ],
        "response": "Je verifie toutes les alertes actives.",
    },
    {
        "tool": "list_alerts",
        "triggers": [
            "liste les alertes", "quelles alertes sont actives",
            "montre mes alertes",
        ],
        "response": "Je liste toutes les alertes configurees.",
    },
    {
        "tool": "delete_alert",
        "triggers": [
            "supprime cette alerte", "enleve l'alerte", "desactive l'alerte",
        ],
        "response": "Je supprime l'alerte demandee.",
    },
    {
        "tool": "send_signal_choices",
        "triggers": [
            "envoie les choix de signaux", "propose les signaux",
        ],
        "response": "J'envoie les choix de signaux pour selection.",
    },

    # ═══════════════════════════════════════════════════════════
    # IA ROUTING — ASK SPECIFIC
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "ask_perplexity",
        "triggers": [
            "demande a Perplexity", "cherche avec Perplexity",
            "question Perplexity", "recherche Perplexity",
        ],
        "response": "J'interroge Perplexity pour une recherche approfondie.",
    },
    {
        "tool": "ask_gemini",
        "triggers": [
            "demande a Gemini", "question pour Gemini",
            "utilise Gemini",
        ],
        "response": "J'interroge Google Gemini.",
    },
    {
        "tool": "ask_lmstudio",
        "triggers": [
            "demande a LM Studio", "question LM Studio locale",
        ],
        "response": "J'interroge LM Studio (modele local).",
    },
    {
        "tool": "ask_claude",
        "triggers": [
            "demande a Claude", "question Claude", "utilise Claude",
        ],
        "response": "J'interroge Claude (Anthropic).",
    },
    {
        "tool": "perplexity_scan",
        "triggers": [
            "scan Perplexity", "recherche approfondie Perplexity",
        ],
        "response": "Je lance un scan via Perplexity.",
    },
    {
        "tool": "get_ia_stats",
        "triggers": [
            "stats des IA", "statistiques IA", "performances des modeles",
        ],
        "response": "J'affiche les statistiques de performance des IA.",
    },

    # ═══════════════════════════════════════════════════════════
    # N8N WORKFLOWS
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "n8n_list_workflows",
        "triggers": [
            "liste les workflows n8n", "quels workflows existent",
            "montre les workflows",
        ],
        "response": "Je liste les workflows n8n disponibles.",
    },
    {
        "tool": "n8n_activate_workflow",
        "triggers": [
            "active ce workflow", "active le workflow n8n",
            "demarre le workflow",
        ],
        "response": "J'active le workflow n8n demande.",
    },
    {
        "tool": "n8n_run_workflow",
        "triggers": [
            "lance ce workflow", "execute le workflow n8n",
            "run le workflow",
        ],
        "response": "J'execute le workflow n8n demande.",
    },
    {
        "tool": "n8n_activate_all",
        "triggers": [
            "active tous les workflows", "demarre tout n8n",
        ],
        "response": "J'active tous les workflows n8n.",
    },
    {
        "tool": "n8n_get_active_workflows",
        "triggers": [
            "workflows actifs", "quels workflows tournent",
        ],
        "response": "Je liste les workflows n8n actuellement actifs.",
    },
    {
        "tool": "open_n8n_dashboard",
        "triggers": [
            "ouvre le dashboard n8n", "ouvre n8n", "interface n8n",
        ],
        "response": "J'ouvre le dashboard n8n dans le navigateur.",
    },

    # ═══════════════════════════════════════════════════════════
    # GITHUB
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "gh_command",
        "triggers": [
            "commande GitHub", "git command", "lance une commande gh",
        ],
        "response": "J'execute la commande GitHub CLI.",
    },
    {
        "tool": "gh_repo_list",
        "triggers": [
            "liste mes repos GitHub", "quels repos j'ai",
            "mes repositories GitHub",
        ],
        "response": "Je liste les repositories GitHub.",
    },

    # ═══════════════════════════════════════════════════════════
    # SQL & DATABASE
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "sql_save_signal",
        "triggers": [
            "sauvegarde ce signal", "enregistre le signal en base",
        ],
        "response": "Je sauvegarde le signal de trading dans la base de donnees.",
    },
    {
        "tool": "sql_get_signals",
        "triggers": [
            "recupere les signaux", "quels signaux en base",
            "montre les signaux enregistres",
        ],
        "response": "Je recupere les signaux de trading depuis la base de donnees.",
    },
    {
        "tool": "sql_top_signals",
        "triggers": [
            "meilleurs signaux", "top signaux en base",
            "signaux les plus performants",
        ],
        "response": "J'affiche les meilleurs signaux de trading en base.",
    },
    {
        "tool": "sql_stats",
        "triggers": [
            "stats de la base", "statistiques SQL", "performance des signaux",
        ],
        "response": "J'affiche les statistiques de la base de donnees de trading.",
    },
    {
        "tool": "sql_query",
        "triggers": [
            "requete SQL", "execute cette requete", "query la base",
        ],
        "response": "J'execute la requete SQL demandee.",
    },
    {
        "tool": "sql_natural_query",
        "triggers": [
            "question en francais sur la base", "combien de signaux gagnants",
            "cherche dans la base en langage naturel",
        ],
        "response": "Je traduis la question en SQL et interroge la base de donnees.",
    },
    {
        "tool": "sql_backup",
        "triggers": [
            "backup la base", "sauvegarde la database",
            "fais un backup SQL",
        ],
        "response": "Je sauvegarde la base de donnees de trading.",
    },
    {
        "tool": "db_get_trades",
        "triggers": [
            "trades en base", "historique trades SQL",
        ],
        "response": "Je recupere les trades depuis la base de donnees.",
    },

    # ═══════════════════════════════════════════════════════════
    # DISPATCHER & CLUSTER
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "dispatcher_status",
        "triggers": [
            "status du dispatcher", "etat du dispatcher",
            "comment va le dispatcher",
        ],
        "response": "J'affiche le status du dispatcher de taches.",
    },
    {
        "tool": "dispatch_task",
        "triggers": [
            "dispatche cette tache", "envoie cette tache au cluster",
        ],
        "response": "Je dispatche la tache au serveur le plus adapte.",
    },
    {
        "tool": "dispatch_parallel_balanced",
        "triggers": [
            "dispatch parallele", "distribue en parallele",
            "equilibre la charge",
        ],
        "response": "Je distribue les taches en parallele de facon equilibree.",
    },
    {
        "tool": "distribute_task",
        "triggers": [
            "distribue cette tache", "envoie au meilleur serveur",
        ],
        "response": "Je distribue la tache au serveur optimal du cluster.",
    },
    {
        "tool": "distributed_scan",
        "triggers": [
            "scan distribue", "scan sur tous les serveurs",
        ],
        "response": "Je lance un scan distribue sur tous les serveurs du cluster.",
    },
    {
        "tool": "dispatch_consensus",
        "triggers": [
            "consensus distribue", "consensus sur le cluster",
        ],
        "response": "Je lance un consensus distribue sur tous les noeuds.",
    },
    {
        "tool": "get_server_metrics",
        "triggers": [
            "metriques des serveurs", "performance des serveurs",
            "charge des serveurs",
        ],
        "response": "J'affiche les metriques de performance des serveurs.",
    },
    {
        "tool": "set_server_priority",
        "triggers": [
            "change la priorite du serveur", "priorite M1 plus haute",
        ],
        "response": "Je modifie la priorite du serveur dans le cluster.",
    },
    {
        "tool": "force_server_failover",
        "triggers": [
            "failover serveur", "bascule vers le backup",
            "force le basculement",
        ],
        "response": "Je force le basculement vers le serveur de secours.",
    },
    {
        "tool": "check_all_lmstudio_servers",
        "triggers": [
            "verifie tous les serveurs LM Studio", "health check cluster",
            "tous les serveurs en ligne",
        ],
        "response": "Je verifie la sante de tous les serveurs LM Studio du cluster.",
    },
    {
        "tool": "health_check_servers",
        "triggers": [
            "health check", "sante des serveurs", "diagnostique le cluster",
        ],
        "response": "Je lance un health check complet de tous les serveurs.",
    },

    # ═══════════════════════════════════════════════════════════
    # LM STUDIO CLI MANAGEMENT
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "lms_list_loaded",
        "triggers": [
            "modeles charges LMS", "quels modeles en memoire",
            "lms list loaded",
        ],
        "response": "Je liste les modeles actuellement charges dans LM Studio.",
    },
    {
        "tool": "lms_list_downloaded",
        "triggers": [
            "modeles telecharges", "quels modeles disponibles localement",
            "modeles sur le disque",
        ],
        "response": "Je liste les modeles telecharges disponibles sur le disque.",
    },
    {
        "tool": "lms_load_model",
        "triggers": [
            "charge ce modele via CLI", "lms load", "load model",
        ],
        "response": "Je charge le modele dans LM Studio via la CLI.",
    },
    {
        "tool": "lms_unload_model",
        "triggers": [
            "decharge ce modele via CLI", "lms unload",
        ],
        "response": "Je decharge le modele de LM Studio via la CLI.",
    },
    {
        "tool": "lms_optimize_m1",
        "triggers": [
            "optimise M1", "configure M1 optimalement",
            "optimisation LM Studio M1",
        ],
        "response": "J'optimise la configuration de M1 pour les meilleures performances.",
    },
    {
        "tool": "lms_auto_configure_cluster",
        "triggers": [
            "auto-configure le cluster", "configure automatiquement",
            "setup optimal du cluster",
        ],
        "response": "Je lance la configuration automatique du cluster LM Studio.",
    },
    {
        "tool": "lms_get_status",
        "triggers": [
            "status LMS", "etat LM Studio CLI",
        ],
        "response": "J'affiche le status de LM Studio via la CLI.",
    },

    # ═══════════════════════════════════════════════════════════
    # CACHE & SYSTEM STATUS
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "get_cache_stats",
        "triggers": [
            "stats du cache", "cache IA", "combien en cache",
        ],
        "response": "J'affiche les statistiques du cache IA.",
    },
    {
        "tool": "clear_ia_cache",
        "triggers": [
            "vide le cache IA", "clear cache", "nettoie le cache",
        ],
        "response": "Je vide le cache IA.",
    },
    {
        "tool": "get_system_status",
        "triggers": [
            "status systeme complet", "etat general", "tout va bien",
            "rapport systeme",
        ],
        "response": "J'affiche le status systeme complet de JARVIS.",
    },
    {
        "tool": "retry_lmstudio_call",
        "triggers": [
            "reessaye l'appel LM Studio", "retry", "relance l'appel",
        ],
        "response": "Je relance l'appel LM Studio avec retry automatique.",
    },
    {
        "tool": "get_filters",
        "triggers": [
            "montre les filtres", "filtres actifs", "configuration des filtres",
        ],
        "response": "J'affiche les filtres de trading actifs.",
    },
    {
        "tool": "update_filter",
        "triggers": [
            "modifie le filtre", "change ce filtre", "update filter",
        ],
        "response": "Je mets a jour le filtre de trading.",
    },

    # ═══════════════════════════════════════════════════════════
    # MISC PIPELINES
    # ═══════════════════════════════════════════════════════════
    {
        "tool": "run_multi_ia_telegram",
        "triggers": [
            "multi-IA Telegram", "envoie le consensus sur Telegram",
            "rapport IA Telegram",
        ],
        "response": "Je lance le pipeline multi-IA et envoie le resultat sur Telegram.",
    },
    {
        "tool": "run_derni_orchestrator",
        "triggers": [
            "lance l'orchestrateur", "orchestrateur Derni",
            "pipeline orchestrateur",
        ],
        "response": "Je lance l'orchestrateur Derni pour coordonner les taches.",
    },
    {
        "tool": "open_browser",
        "triggers": [
            "ouvre le navigateur", "lance Chrome", "ouvre un site web",
        ],
        "response": "J'ouvre le navigateur web.",
    },
    {
        "tool": "get_all_workflows",
        "triggers": [
            "tous les workflows", "montre tous les workflows disponibles",
        ],
        "response": "J'affiche tous les workflows disponibles.",
    },
]


def generate_conversations() -> list[dict]:
    """Genere les conversations de tool routing MCP."""
    convs = []
    for ex in MCP_TOOL_EXAMPLES:
        tool_name = ex["tool"]
        response = ex["response"]
        for trigger in ex["triggers"]:
            convs.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": trigger},
                    {"role": "assistant", "content": response},
                ]
            })
            convs.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": trigger},
                    {"role": "assistant", "content": f"{response}\n\n[Outil : {tool_name}]"},
                ]
            })
    return convs


def enrich_dataset(convs: list[dict]):
    """Ajoute au dataset existant."""
    train_path = OUTPUT_DIR / "jarvis_finetune_train.jsonl"
    eval_path = OUTPUT_DIR / "jarvis_finetune_eval.jsonl"

    if not train_path.exists():
        print("[ERREUR] Dataset non trouve !")
        return

    with open(train_path, "r", encoding="utf-8") as f:
        existing_train = [json.loads(l) for l in f]
    with open(eval_path, "r", encoding="utf-8") as f:
        existing_eval = [json.loads(l) for l in f]

    random.seed(43)
    random.shuffle(convs)
    split = int(len(convs) * 0.95)

    all_train = existing_train + convs[:split]
    all_eval = existing_eval + convs[split:]

    random.shuffle(all_train)
    random.shuffle(all_eval)

    for data, path in [(all_train, train_path), (all_eval, eval_path)]:
        with open(path, "w", encoding="utf-8") as f:
            for conv in data:
                f.write(json.dumps(conv, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"Dataset enrichi avec MCP tools !")
    print(f"  MCP tools: {len(MCP_TOOL_EXAMPLES)} outils, {len(convs)} exemples")
    print(f"  Train : {len(all_train)} (avant: {len(existing_train)})")
    print(f"  Eval  : {len(all_eval)} (avant: {len(existing_eval)})")
    print(f"  Ajout : +{len(convs)}")
    print(f"{'='*60}")


def main():
    print("=" * 60)
    print("JARVIS Fine-Tuning — Enrichissement MCP Tools")
    print("=" * 60)

    convs = generate_conversations()
    print(f"\n[OK] {len(convs)} exemples MCP generes ({len(MCP_TOOL_EXAMPLES)} outils)")
    enrich_dataset(convs)


if __name__ == "__main__":
    main()
