#!/usr/bin/env python3
"""Deploy COWORK Pattern Agents — Creates 30 pattern agents from 331 cowork scripts.
Maps every script to a specialized pattern agent in etoile.db.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'etoile.db')
COWORK_DEV = os.path.join(os.path.dirname(__file__), 'dev')

# === 30 COWORK PATTERN AGENTS ===
COWORK_PATTERNS = {
    # --- WINDOWS (8 patterns) ---
    "PAT_CW_WIN_MONITORING": {
        "agent_id": "cw-win-monitoring",
        "pattern_type": "win_monitoring",
        "keywords": "thermal,gpu,vram,temperature,memoire,ram,cpu,disque,io,evenement,monitoring,profiler",
        "description": "COWORK Windows Monitoring — thermal GPU, memoire, CPU, I/O disque, evenements systeme",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "win_thermal_monitor", "win_memory_profiler", "win_event_monitor", "win_event_watcher",
            "win_io_analyzer", "win_performance_tuner", "win_battery_monitor", "win_disk_analyzer",
            "gpu_thermal_guard", "gpu_optimizer", "win_app_usage_tracker", "win_crash_analyzer"
        ]
    },
    "PAT_CW_WIN_NETWORK": {
        "agent_id": "cw-win-network",
        "pattern_type": "win_network",
        "keywords": "reseau,network,firewall,wifi,dns,vpn,connexion,port,tcp,ip,ping,bandwidth",
        "description": "COWORK Windows Network — firewall, WiFi, DNS, VPN, analyse reseau",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M3:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_network_analyzer", "win_network_guard", "win_firewall_analyzer", "win_firewall_manager",
            "win_wifi_analyzer", "win_vpn_monitor", "win_dns_cache_manager", "network_monitor",
            "network_optimizer", "wifi_manager"
        ]
    },
    "PAT_CW_WIN_SYSTEM": {
        "agent_id": "cw-win-system",
        "pattern_type": "win_system",
        "keywords": "service,processus,registre,startup,boot,tache,planifiee,driver,wsl,systeme",
        "description": "COWORK Windows System — services, processus, registre, startup, drivers, WSL",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_service_analyzer", "win_service_monitor", "win_service_watchdog", "win_process_analyzer",
            "win_process_guardian", "win_registry_guard", "win_registry_guardian", "win_scheduled_task_auditor",
            "win_startup_optimizer", "win_startup_profiler", "win_boot_optimizer", "win_driver_checker",
            "win_wsl_manager", "win_env_auditor", "driver_checker", "process_manager",
            "service_watchdog", "service_watcher", "windows_service_hardener", "windows_integration_agent",
            "startup_manager", "scheduled_task_creator"
        ]
    },
    "PAT_CW_WIN_DESKTOP": {
        "agent_id": "cw-win-desktop",
        "pattern_type": "win_desktop",
        "keywords": "fenetre,ecran,clipboard,audio,son,bureau,virtual,workspace,focus,raccourci,geste,hotkey",
        "description": "COWORK Windows Desktop — fenetres, ecrans, clipboard, audio, bureaux virtuels",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,OL1:qwen3:1.7b",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_window_manager", "win_display_manager", "win_screen_analyzer", "win_screen_recorder",
            "win_clipboard_history", "win_clipboard_ai", "win_audio_controller", "win_sound_mixer",
            "win_virtual_desktop", "win_workspace_profiles", "win_focus_timer", "win_hotkey_engine",
            "win_gesture_detector", "win_shortcut_manager", "win_context_menu", "window_manager",
            "display_manager", "audio_controller", "clipboard_history", "desktop_organizer",
            "desktop_workflow_builder"
        ]
    },
    "PAT_CW_WIN_SECURITY": {
        "agent_id": "cw-win-security",
        "pattern_type": "win_security",
        "keywords": "backup,defender,privacy,certificat,securite,antivirus,guard,protection,chiffrement",
        "description": "COWORK Windows Security — backup, Defender, privacy, certificats, protection",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 4,
        "scripts": [
            "win_backup", "win_backup_manager", "win_defender_monitor", "win_privacy_guard",
            "win_certificate_checker", "security_scanner", "win_system_restore_manager"
        ]
    },
    "PAT_CW_WIN_AUTOMATION": {
        "agent_id": "cw-win-automation",
        "pattern_type": "win_automation",
        "keywords": "launcher,app,tache,automatise,quick,action,schedule,task",
        "description": "COWORK Windows Automation — lanceurs intelligents, taches automatisees",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,OL1:qwen3:1.7b",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_app_controller", "win_smart_launcher", "win_smart_launcher_v2", "win_quick_actions",
            "win_task_automator", "win_task_scheduler_pro", "smart_launcher", "task_automator"
        ]
    },
    "PAT_CW_WIN_MAINTENANCE": {
        "agent_id": "cw-win-maintenance",
        "pattern_type": "win_maintenance",
        "keywords": "nettoyage,temp,defrag,pagefile,power,update,restore,optimisation,maintenance",
        "description": "COWORK Windows Maintenance — nettoyage, defrag, pagefile, updates, restauration",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M3:deepseek-r1,OL1:qwen3:1.7b",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_optimizer", "win_temp_cleaner", "win_defrag_scheduler", "win_pagefile_optimizer",
            "win_power_optimizer", "win_power_plan_manager", "win_update_tracker",
            "win_recycle_bin_manager", "power_manager", "system_restore"
        ]
    },
    "PAT_CW_WIN_MEDIA": {
        "agent_id": "cw-win-media",
        "pattern_type": "win_media",
        "keywords": "media,font,imprimante,notification,tts,game,peripherique,usb,bluetooth,fichier",
        "description": "COWORK Windows Media — fichiers media, polices, imprimantes, peripheriques",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "OL1:qwen3:1.7b,M3:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_media_organizer", "win_font_manager", "win_printer_manager", "win_notification_ai",
            "win_game_mode_manager", "win_peripheral_manager", "win_tts", "win_ai_copilot",
            "win_copilot_bridge", "win_accessibility_enhancer", "win_notify",
            "bluetooth_manager", "usb_monitor", "file_organizer", "screenshot_tool"
        ]
    },

    # --- JARVIS (8 patterns) ---
    "PAT_CW_JARVIS_CORE": {
        "agent_id": "cw-jarvis-core",
        "pattern_type": "jarvis_core",
        "keywords": "config,state,rule,plugin,template,preload,api,gateway,jarvis,core",
        "description": "COWORK JARVIS Core — config, state machine, rules, plugins, templates, API",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "jarvis_state_machine", "jarvis_config_center", "jarvis_config_validator",
            "jarvis_rule_engine", "jarvis_plugin_tester", "jarvis_template_engine",
            "jarvis_preloader", "jarvis_api_gateway", "config_validator"
        ]
    },
    "PAT_CW_JARVIS_VOICE": {
        "agent_id": "cw-jarvis-voice",
        "pattern_type": "jarvis_voice",
        "keywords": "voix,vocal,wake,word,dictation,tts,voice,profile,whisper,audio,parle",
        "description": "COWORK JARVIS Voice — wake word, profils vocaux, dictation, TTS, pipeline audio",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,OL1:qwen3:1.7b",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "jarvis_wake_word_tuner", "jarvis_voice_profile", "jarvis_voice_trainer",
            "jarvis_dictation_mode", "jarvis_tts_cache_manager", "tts_cache_manager",
            "voice_enhancer", "voice_gap_filler", "voice_pipeline_optimizer",
            "voice_browser_nav", "voice_trainer", "domino_executor"
        ]
    },
    "PAT_CW_JARVIS_NLP": {
        "agent_id": "cw-jarvis-nlp",
        "pattern_type": "jarvis_nlp",
        "keywords": "intent,nlp,sentiment,conversation,dialog,langue,classifieur,analyse,texte",
        "description": "COWORK JARVIS NLP — intent, sentiment, conversation, dialog, multi-langue",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "jarvis_nlp_enhancer", "jarvis_intent_classifier", "jarvis_intent_predictor",
            "jarvis_intent_router", "jarvis_sentiment_analyzer", "jarvis_conversation_analyzer",
            "jarvis_conversation_memory", "jarvis_dialog_manager", "jarvis_multi_language",
            "jarvis_personality_engine", "intent_classifier", "conversation_manager",
            "ai_conversation", "interaction_predictor"
        ]
    },
    "PAT_CW_JARVIS_DEVOPS": {
        "agent_id": "cw-jarvis-devops",
        "pattern_type": "jarvis_devops",
        "keywords": "backup,changelog,permission,secret,audit,migration,release,test,deploy",
        "description": "COWORK JARVIS DevOps — backup, changelog, permissions, secrets, release",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "jarvis_backup_manager", "jarvis_changelog_generator", "jarvis_permission_auditor",
            "jarvis_secret_scanner", "jarvis_code_auditor", "jarvis_db_migrator",
            "jarvis_release_manager", "jarvis_self_test_suite", "jarvis_dependency_mapper",
            "jarvis_update_checker", "deployment_manager"
        ]
    },
    "PAT_CW_JARVIS_INTELLIGENCE": {
        "agent_id": "cw-jarvis-intelligence",
        "pattern_type": "jarvis_intelligence",
        "keywords": "pattern,cache,response,ab,test,predict,brain,memory,embedding,command",
        "description": "COWORK JARVIS Intelligence — patterns, cache, A/B test, prediction, brain, embedding",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 3,
        "scripts": [
            "jarvis_pattern_learner", "jarvis_pattern_miner", "jarvis_response_cache",
            "jarvis_response_profiler", "jarvis_ab_tester", "jarvis_command_predictor",
            "jarvis_brain", "jarvis_memory_optimizer", "jarvis_embedding_engine",
            "jarvis_context_engine", "context_engine", "prediction_trainer"
        ]
    },
    "PAT_CW_JARVIS_PIPES": {
        "agent_id": "cw-jarvis-pipes",
        "pattern_type": "jarvis_pipes",
        "keywords": "cron,macro,webhook,event,notification,message,pipeline,route,stream",
        "description": "COWORK JARVIS Pipelines — crons, macros, webhooks, events, notifications",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,OL1:qwen3:1.7b",
        "strategy": "category",
        "priority": 3,
        "scripts": [
            "jarvis_cron_optimizer", "jarvis_macro_recorder", "jarvis_webhook_manager",
            "jarvis_webhook_server", "jarvis_event_stream", "jarvis_notification_hub",
            "jarvis_notification_router", "jarvis_message_router", "jarvis_pipeline_monitor",
            "event_bus_monitor", "event_logger", "notification_hub", "pipeline_orchestrator",
            "smart_cron_manager"
        ]
    },
    "PAT_CW_JARVIS_EVOLVE": {
        "agent_id": "cw-jarvis-evolve",
        "pattern_type": "jarvis_evolve",
        "keywords": "evolve,improve,self,skill,generator,feature,autonomy,night",
        "description": "COWORK JARVIS Self-Evolution — auto-amelioration, skills generation, evolution",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 4,
        "scripts": [
            "jarvis_self_evolve", "jarvis_self_improve", "jarvis_self_improver",
            "jarvis_evolution_engine", "jarvis_skill_generator", "jarvis_skill_recommender",
            "jarvis_feature_builder", "jarvis_autonomy_engine", "jarvis_autonomy_monitor",
            "jarvis_night_ops", "self_feeding_engine", "self_improver"
        ]
    },
    "PAT_CW_JARVIS_DASHBOARD": {
        "agent_id": "cw-jarvis-dashboard",
        "pattern_type": "jarvis_dashboard",
        "keywords": "dashboard,health,analytics,performance,roi,briefing,ecosystem,orchestrator,meta",
        "description": "COWORK JARVIS Dashboard — meta dashboard, health, analytics, ROI, briefing",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,OL1:qwen3:1.7b",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "jarvis_meta_dashboard", "jarvis_health_aggregator", "jarvis_usage_analytics",
            "jarvis_performance_tracker", "jarvis_roi_calculator", "jarvis_daily_briefing",
            "jarvis_ecosystem_map", "jarvis_orchestrator_v3", "jarvis_log_analyzer",
            "jarvis_data_exporter", "jarvis_telegram_enhanced", "jarvis_faq_builder",
            "jarvis_wiki_engine", "dashboard_generator", "usage_analytics"
        ]
    },

    # --- IA AUTONOME (5 patterns) ---
    "PAT_CW_IA_GENERATION": {
        "agent_id": "cw-ia-generation",
        "pattern_type": "ia_generation",
        "keywords": "genere,code,doc,test,story,image,prompt,data,synthetise,autonome,coder",
        "description": "COWORK IA Generation — code, docs, tests, stories, images, data synthesis",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 3,
        "scripts": [
            "ia_code_generator", "ia_code_generator_v2", "ia_doc_writer", "ia_doc_generator",
            "ia_test_writer", "ia_test_generator", "ia_story_generator", "ia_image_prompt_crafter",
            "ia_data_synthesizer", "ia_autonomous_coder", "code_generator", "generate_docstrings"
        ]
    },
    "PAT_CW_IA_OPTIMIZATION": {
        "agent_id": "cw-ia-optimization",
        "pattern_type": "ia_optimization",
        "keywords": "prompt,meta,cost,routing,weight,inference,cache,model,benchmark,workload,balance",
        "description": "COWORK IA Optimization — prompts, couts, routing, poids, inference, benchmark",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "ia_prompt_optimizer", "ia_meta_optimizer", "ia_cost_tracker", "ia_routing_optimizer",
            "ia_weight_calibrator", "ia_inference_profiler", "ia_model_cache_manager",
            "ia_model_benchmarker", "ia_workload_balancer", "ia_usage_predictor",
            "prompt_optimizer", "response_evaluator"
        ]
    },
    "PAT_CW_IA_LEARNING": {
        "agent_id": "cw-ia-learning",
        "pattern_type": "ia_learning",
        "keywords": "apprend,critic,distill,curriculum,transfer,feedback,memory,skill,teacher,student,capability",
        "description": "COWORK IA Learning — auto-critique, distillation, curriculum, transfer learning",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 4,
        "scripts": [
            "ia_self_critic", "ia_self_improver", "ia_knowledge_distiller", "ia_curriculum_planner",
            "ia_transfer_learner", "ia_feedback_loop", "ia_memory_consolidator",
            "ia_skill_synthesizer", "ia_teacher_student", "ia_capability_tracker",
            "continuous_learner", "task_learner"
        ]
    },
    "PAT_CW_IA_ORCHESTRATION": {
        "agent_id": "cw-ia-orchestration",
        "pattern_type": "ia_orchestration",
        "keywords": "swarm,agent,spawn,ensemble,vote,debate,peer,review,task,plan,goal,decompose",
        "description": "COWORK IA Orchestration — swarm, agents, ensemble voting, debate, goals",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 3,
        "scripts": [
            "ia_swarm_coordinator", "ia_agent_spawner", "ia_ensemble_voter", "ia_debate_engine",
            "ia_peer_reviewer", "ia_task_planner", "ia_task_prioritizer", "ia_goal_decomposer",
            "ia_goal_tracker", "multi_agent_coordinator", "agent_orchestrator"
        ]
    },
    "PAT_CW_IA_ANALYSIS": {
        "agent_id": "cw-ia-analysis",
        "pattern_type": "ia_analysis",
        "keywords": "anomalie,fact,check,hypothese,experiment,erreur,pattern,detect,chain,thought,proactif",
        "description": "COWORK IA Analysis — anomalies, fact-check, hypotheses, experiments, CoT",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 3,
        "scripts": [
            "ia_anomaly_detector", "ia_fact_checker", "ia_hypothesis_tester", "ia_experiment_runner",
            "ia_error_analyzer", "ia_pattern_detector", "ia_chain_of_thought",
            "ia_chain_of_thought_v2", "ia_proactive_agent", "ia_knowledge_graph",
            "anomaly_detector", "decision_engine"
        ]
    },

    # --- INFRA & OPS (6 patterns) ---
    "PAT_CW_CLUSTER": {
        "agent_id": "cw-cluster",
        "pattern_type": "cluster_mgmt",
        "keywords": "cluster,autotuner,benchmark,failover,load,predict,model,rotator,sync,noeud",
        "description": "COWORK Cluster Management — autotuner, benchmark, failover, load prediction, sync",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "cluster_autotuner", "cluster_benchmark_auto", "cluster_dashboard_api",
            "cluster_failover_manager", "cluster_load_predictor", "cluster_model_rotator",
            "cluster_sync", "node_balancer", "load_balancer", "model_manager",
            "model_benchmark", "model_rotator"
        ]
    },
    "PAT_CW_TRADING": {
        "agent_id": "cw-trading",
        "pattern_type": "trading_full",
        "keywords": "trading,crypto,signal,backtest,portfolio,risk,mexc,strategie,marche",
        "description": "COWORK Trading Pipeline — signaux, backtest, portfolio, risk management",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M2:deepseek-r1,M1B:gpt-oss-20b",
        "strategy": "single",
        "priority": 4,
        "scripts": [
            "auto_trader", "trading_intelligence", "signal_backtester",
            "portfolio_tracker", "risk_manager"
        ]
    },
    "PAT_CW_COMMS": {
        "agent_id": "cw-comms",
        "pattern_type": "communications",
        "keywords": "telegram,email,mail,rapport,message,envoie,notification,bot",
        "description": "COWORK Communications — Telegram, email, rapports, notifications",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,OL1:qwen3:1.7b",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "telegram_commander", "telegram_bot_monitor", "telegram_scheduler",
            "telegram_stats", "email_reader", "report_mailer", "cross_channel_sync"
        ]
    },
    "PAT_CW_DEVTOOLS": {
        "agent_id": "cw-devtools",
        "pattern_type": "devtools",
        "keywords": "code,review,test,continu,mcp,tool,generate,docstring,coder",
        "description": "COWORK DevTools — code generation, review, tests continus, MCP testing",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 3,
        "scripts": [
            "code_reviewer", "continuous_coder", "continuous_test_runner",
            "test_generator", "mcp_tool_tester", "jarvis_test_generator"
        ]
    },
    "PAT_CW_AUTONOMOUS": {
        "agent_id": "cw-autonomous",
        "pattern_type": "autonomous_ops",
        "keywords": "auto,autonome,scheduler,monitor,healer,deploy,dispatch,documenter,skill,update,reporter",
        "description": "COWORK Autonomous Ops — scheduler, monitor, healer, deployer, auto-learning",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "category",
        "priority": 2,
        "scripts": [
            "auto_scheduler", "auto_monitor", "auto_healer", "auto_deployer",
            "auto_dispatcher", "auto_documenter", "auto_skill_tester", "auto_updater",
            "auto_reporter", "auto_learner", "autonomous_health_guard", "proactive_agent",
            "openclaw_watchdog"
        ]
    },
    "PAT_CW_DATA": {
        "agent_id": "cw-data",
        "pattern_type": "data_management",
        "keywords": "db,database,export,import,knowledge,graph,metrics,analytics,donnees,sqlite,log",
        "description": "COWORK Data Management — DB optimization, exports, knowledge graph, metrics",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M3:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "db_optimizer", "data_exporter", "knowledge_graph", "knowledge_updater",
            "metrics_collector", "log_analyzer", "log_rotator", "alert_manager",
            "api_monitor", "health_checker", "memory_optimizer", "performance_profiler",
            "system_benchmark", "resource_forecaster", "electron_app_monitor"
        ]
    },

    # --- SPECIAL (3 patterns) ---
    "PAT_CW_ROUTING": {
        "agent_id": "cw-routing",
        "pattern_type": "routing_mgmt",
        "keywords": "route,prompt,node,balance,model,dispatch,coordinate,orchestrate,intent",
        "description": "COWORK Routing — prompt routing, node balancing, model management, orchestration",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "M1B:gpt-oss-20b,M2:deepseek-r1",
        "strategy": "single",
        "priority": 2,
        "scripts": [
            "prompt_router", "auto_dispatcher", "workspace_analyzer", "workspace_sync"
        ]
    },
    "PAT_CW_BROWSER": {
        "agent_id": "cw-browser",
        "pattern_type": "browser_ops",
        "keywords": "browser,navigateur,chrome,edge,automation,macro,pilot,web",
        "description": "COWORK Browser — automation navigateur, macros, pilotage Chrome/Edge",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "OL1:qwen3:1.7b,M3:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "browser_automation", "browser_pilot"
        ]
    },
    "PAT_CW_FILE_WATCH": {
        "agent_id": "cw-file-watch",
        "pattern_type": "file_watch",
        "keywords": "fichier,file,watch,backup,organise,sync,rotate,clean",
        "description": "COWORK File Watch — surveillance fichiers, backups, organisation, rotation logs",
        "model_primary": "qwen3-8b",
        "model_fallbacks": "OL1:qwen3:1.7b,M3:deepseek-r1",
        "strategy": "single",
        "priority": 3,
        "scripts": [
            "win_file_watcher", "win_file_watcher_v2"
        ]
    },
}


def deploy():
    """Insert all COWORK pattern agents into etoile.db."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    now = datetime.now().isoformat()

    # Ensure script_mapping table exists (maps scripts to patterns)
    db.execute("""
        CREATE TABLE IF NOT EXISTS cowork_script_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_name TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            script_path TEXT,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(script_name, pattern_id)
        )
    """)

    inserted = 0
    updated = 0
    scripts_mapped = 0

    for pat_id, pat in COWORK_PATTERNS.items():
        # Insert or update pattern agent
        existing = db.execute(
            "SELECT id FROM agent_patterns WHERE pattern_id = ?", (pat_id,)
        ).fetchone()

        if existing:
            db.execute("""
                UPDATE agent_patterns SET
                    agent_id = ?, pattern_type = ?, keywords = ?, description = ?,
                    model_primary = ?, model_fallbacks = ?, strategy = ?,
                    priority = ?, updated_at = ?
                WHERE pattern_id = ?
            """, (
                pat["agent_id"], pat["pattern_type"], pat["keywords"],
                pat["description"], pat["model_primary"], pat["model_fallbacks"],
                pat["strategy"], pat["priority"], now, pat_id
            ))
            updated += 1
        else:
            db.execute("""
                INSERT INTO agent_patterns
                    (pattern_id, agent_id, pattern_type, keywords, description,
                     model_primary, model_fallbacks, strategy, priority, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pat_id, pat["agent_id"], pat["pattern_type"], pat["keywords"],
                pat["description"], pat["model_primary"], pat["model_fallbacks"],
                pat["strategy"], pat["priority"], now, now
            ))
            inserted += 1

        # Map scripts to pattern
        for script in pat.get("scripts", []):
            script_path = os.path.join(COWORK_DEV, f"{script}.py")
            exists = os.path.exists(script_path)
            try:
                db.execute("""
                    INSERT OR IGNORE INTO cowork_script_mapping
                        (script_name, pattern_id, script_path, status)
                    VALUES (?, ?, ?, ?)
                """, (script, pat_id, script_path if exists else None,
                      "active" if exists else "missing"))
                scripts_mapped += 1
            except sqlite3.IntegrityError:
                pass

    db.commit()

    # Stats
    total_patterns = db.execute("SELECT COUNT(*) FROM agent_patterns").fetchone()[0]
    total_cowork = db.execute(
        "SELECT COUNT(*) FROM agent_patterns WHERE pattern_id LIKE 'PAT_CW_%'"
    ).fetchone()[0]
    total_scripts = db.execute(
        "SELECT COUNT(*) FROM cowork_script_mapping"
    ).fetchone()[0]

    db.close()

    result = {
        "status": "OK",
        "patterns_inserted": inserted,
        "patterns_updated": updated,
        "scripts_mapped": scripts_mapped,
        "total_patterns_db": total_patterns,
        "total_cowork_patterns": total_cowork,
        "total_scripts_mapped": total_scripts,
        "timestamp": now
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def status():
    """Show deployment status."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    print("\n=== COWORK Pattern Agents ===\n")
    rows = db.execute("""
        SELECT pattern_id, agent_id, pattern_type, description, strategy, priority,
               total_calls, success_rate
        FROM agent_patterns WHERE pattern_id LIKE 'PAT_CW_%'
        ORDER BY pattern_id
    """).fetchall()

    for r in rows:
        print(f"  {r['pattern_id']:35s} | {r['agent_id']:25s} | "
              f"strat={r['strategy']:8s} prio={r['priority']} "
              f"calls={r['total_calls']} rate={r['success_rate']:.0%}")

    print(f"\n  Total: {len(rows)} COWORK patterns")

    # Script mapping stats
    try:
        mapping = db.execute("""
            SELECT pattern_id, COUNT(*) as cnt
            FROM cowork_script_mapping
            GROUP BY pattern_id
            ORDER BY cnt DESC
        """).fetchall()
        print(f"\n=== Script Mapping ===\n")
        for m in mapping:
            print(f"  {m['pattern_id']:35s} → {m['cnt']} scripts")
    except:
        pass

    db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deploy COWORK Pattern Agents")
    parser.add_argument("--deploy", action="store_true", help="Deploy all patterns to etoile.db")
    parser.add_argument("--status", action="store_true", help="Show deployment status")
    parser.add_argument("--once", action="store_true", help="Deploy once (alias)")
    args = parser.parse_args()

    if args.deploy or args.once or len(sys.argv) == 1:
        deploy()
    if args.status:
        status()
