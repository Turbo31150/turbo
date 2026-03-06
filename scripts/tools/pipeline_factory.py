"""
PIPELINE FACTORY v1.0 — Generateur massif de pipelines domino cycliques
Insere dans data/etoile.db et data/jarvis.db
Preserve les pipelines existants, ajoute de nouveaux.
"""
import sqlite3
import json
import sys
import io
import os
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETOILE_DB = os.path.join(BASE, "data", "etoile.db")
JARVIS_DB = os.path.join(BASE, "data", "jarvis.db")

# ══════════════════════════════════════════════════════════════════════════════
# NODES REFERENCE
# ══════════════════════════════════════════════════════════════════════════════
NODES = ["M1", "M2", "M3", "OL1", "GEMINI", "CLAUDE"]
NODE_WEIGHTS = {"M1": 1.8, "M2": 1.4, "OL1": 1.3, "GEMINI": 1.2, "CLAUDE": 1.2, "M3": 1.0}

# ══════════════════════════════════════════════════════════════════════════════
# 1. PIPELINES — ~600 nouveaux pipelines multi-step multi-agent
# ══════════════════════════════════════════════════════════════════════════════

def gen_pipelines():
    """Generate all new pipelines."""
    pipes = []

    # ── CLUSTER OPS (60 pipelines) ──
    cluster_ops = [
        ("cluster_health_full", "diagnostic complet du cluster", "jarvis_tool:cluster_check;;sleep:2;;jarvis_tool:gpu_status;;sleep:1;;jarvis_tool:thermal_check", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_heal_auto", "repare le cluster automatiquement", "jarvis_tool:cluster_check;;sleep:1;;jarvis_tool:heal_cluster;;sleep:3;;jarvis_tool:cluster_check", "pipeline", "M1,M2,M3"),
        ("cluster_benchmark_cycle", "benchmark et optimise le cluster", "jarvis_tool:cluster_benchmark;;sleep:5;;jarvis_tool:scores;;sleep:1;;jarvis_tool:optimize_routing", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_thermal_monitor", "surveille les temperatures gpu", "jarvis_tool:thermal_check;;sleep:2;;jarvis_tool:gpu_status;;sleep:1;;jarvis_tool:log_thermal", "pipeline", "M1,M2,M3"),
        ("cluster_vram_check", "verifie la vram de toutes les machines", "jarvis_tool:gpu_status;;sleep:1;;jarvis_tool:vram_report", "pipeline", "M1,M2,M3"),
        ("cluster_model_reload", "recharge les modeles sur le cluster", "jarvis_tool:model_swap_unload;;sleep:3;;jarvis_tool:model_swap_load;;sleep:5;;jarvis_tool:cluster_check", "pipeline", "M1,M2,M3"),
        ("cluster_latency_test", "teste la latence de tous les noeuds", "jarvis_tool:quick_ask M1;;jarvis_tool:quick_ask M2;;jarvis_tool:quick_ask M3;;jarvis_tool:quick_ask OL1", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_consensus_test", "teste le consensus multi-agents", "jarvis_tool:consensus test rapide;;sleep:5;;jarvis_tool:log_consensus", "pipeline", "M1,M2,M3,OL1,GEMINI"),
        ("cluster_failover_drill", "simule une panne et teste le failover", "jarvis_tool:simulate_fail M3;;sleep:2;;jarvis_tool:cluster_check;;sleep:1;;jarvis_tool:heal_cluster;;sleep:3;;jarvis_tool:cluster_check", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_daily_report", "genere le rapport quotidien du cluster", "jarvis_tool:cluster_check;;sleep:1;;jarvis_tool:gpu_status;;sleep:1;;jarvis_tool:benchmark_summary;;sleep:1;;jarvis_tool:save_report", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_node_compare", "compare les performances des noeuds", "jarvis_tool:bench_node M1;;jarvis_tool:bench_node M2;;jarvis_tool:bench_node M3;;jarvis_tool:bench_node OL1;;sleep:3;;jarvis_tool:compare_scores", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_routing_optimize", "optimise le routage dynamique", "jarvis_tool:autolearn_status;;sleep:1;;jarvis_tool:routing_analysis;;sleep:1;;jarvis_tool:update_weights", "pipeline", "M1,M2"),
        ("cluster_backup_config", "sauvegarde la config du cluster", "jarvis_tool:export_config;;sleep:1;;jarvis_tool:backup_db;;sleep:1;;jarvis_tool:git_commit_backup", "pipeline", "M1"),
        ("cluster_stress_test", "stress test le cluster entier", "jarvis_tool:stress M1;;jarvis_tool:stress M2;;jarvis_tool:stress M3;;sleep:10;;jarvis_tool:thermal_check;;jarvis_tool:benchmark_summary", "pipeline", "M1,M2,M3"),
        ("cluster_cold_start", "demarre le cluster a froid", "jarvis_tool:wake_m2;;sleep:5;;jarvis_tool:wake_m3;;sleep:5;;jarvis_tool:cluster_check;;sleep:2;;jarvis_tool:model_swap_load", "pipeline", "M1,M2,M3"),
        ("cluster_graceful_shutdown", "arrete le cluster proprement", "jarvis_tool:save_state;;sleep:1;;jarvis_tool:model_swap_unload;;sleep:3;;jarvis_tool:notify_shutdown", "pipeline", "M1,M2,M3"),
        ("cluster_network_diag", "diagnostic reseau du cluster", "powershell:Test-Connection 192.168.1.26 -Count 2;;powershell:Test-Connection 192.168.1.113 -Count 2;;powershell:Test-Connection 10.5.0.2 -Count 2;;jarvis_tool:network_report", "pipeline", "M1,M2,M3"),
        ("cluster_sync_models", "synchronise les modeles entre machines", "jarvis_tool:list_models M1;;jarvis_tool:list_models M2;;jarvis_tool:list_models M3;;jarvis_tool:sync_report", "pipeline", "M1,M2,M3"),
        ("cluster_perf_baseline", "etablit une baseline de performance", "jarvis_tool:bench_quick M1;;jarvis_tool:bench_quick M2;;jarvis_tool:bench_quick M3;;jarvis_tool:bench_quick OL1;;jarvis_tool:save_baseline", "pipeline", "M1,M2,M3,OL1"),
        ("cluster_alert_setup", "configure les alertes du cluster", "jarvis_tool:set_alert thermal 75;;jarvis_tool:set_alert vram 90;;jarvis_tool:set_alert latency 5000;;jarvis_tool:alert_status", "pipeline", "M1"),
    ]
    for pid, trigger, steps, atype, agents in cluster_ops:
        pipes.append((pid, trigger, steps, "cluster_ops", atype, agents))

    # ── DEVOPS (50 pipelines) ──
    devops = [
        ("devops_git_push_cycle", "commit et push le projet", "powershell:cd F:\\BUREAU\\turbo; git add -A;;powershell:cd F:\\BUREAU\\turbo; git status;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; git commit -m 'auto-commit';;powershell:cd F:\\BUREAU\\turbo; git push", "pipeline", "M1"),
        ("devops_test_suite", "lance la suite de tests", "powershell:cd F:\\BUREAU\\turbo; python -m pytest tests/ -v;;sleep:5;;jarvis_tool:test_report", "pipeline", "M1,M2"),
        ("devops_lint_fix", "lint et corrige le code", "powershell:cd F:\\BUREAU\\turbo; python -m ruff check src/ --fix;;sleep:2;;jarvis_tool:lint_report", "pipeline", "M1"),
        ("devops_docker_deploy", "deploie avec docker", "powershell:cd F:\\BUREAU\\turbo; docker-compose build;;sleep:10;;powershell:cd F:\\BUREAU\\turbo; docker-compose up -d;;sleep:5;;jarvis_tool:docker_status", "pipeline", "M1"),
        ("devops_build_electron", "compile l'app electron", "powershell:cd F:\\BUREAU\\turbo\\electron; npm run build;;sleep:15;;jarvis_tool:build_report", "pipeline", "M1"),
        ("devops_update_deps", "met a jour les dependances", "powershell:cd F:\\BUREAU\\turbo; uv sync;;sleep:5;;powershell:cd F:\\BUREAU\\turbo\\electron; npm update;;sleep:5;;jarvis_tool:dep_report", "pipeline", "M1"),
        ("devops_code_review_cycle", "revue de code automatique", "jarvis_tool:git_diff;;sleep:1;;jarvis_tool:code_review M2;;sleep:5;;jarvis_tool:code_review GEMINI;;sleep:5;;jarvis_tool:merge_reviews", "pipeline", "M2,GEMINI"),
        ("devops_security_scan", "scan de securite du code", "powershell:cd F:\\BUREAU\\turbo; python -m bandit -r src/ -f json;;sleep:5;;jarvis_tool:security_report", "pipeline", "M1,GEMINI"),
        ("devops_db_migrate", "migration de base de donnees", "jarvis_tool:backup_db;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; python scripts/migrate_db.py;;sleep:3;;jarvis_tool:db_verify", "pipeline", "M1"),
        ("devops_release_cycle", "cycle complet de release", "jarvis_tool:test_suite;;sleep:10;;jarvis_tool:lint_fix;;sleep:3;;jarvis_tool:build_electron;;sleep:15;;jarvis_tool:git_tag_release;;jarvis_tool:deploy_notify", "pipeline", "M1,M2"),
        ("devops_hotfix", "hotfix rapide", "jarvis_tool:git_stash;;jarvis_tool:git_checkout_main;;sleep:1;;jarvis_tool:apply_fix;;jarvis_tool:test_quick;;jarvis_tool:git_push", "pipeline", "M1"),
        ("devops_branch_cleanup", "nettoie les branches git", "powershell:cd F:\\BUREAU\\turbo; git fetch --prune;;powershell:cd F:\\BUREAU\\turbo; git branch --merged | findstr /v main | ForEach-Object { git branch -d $_.Trim() }", "pipeline", "M1"),
        ("devops_perf_profile", "profile de performance du code", "powershell:cd F:\\BUREAU\\turbo; python -m cProfile -o data/profile.out src/main.py;;sleep:10;;jarvis_tool:profile_report", "pipeline", "M1"),
        ("devops_doc_gen", "genere la documentation", "jarvis_tool:scan_codebase;;sleep:3;;jarvis_tool:gen_api_doc M1;;sleep:5;;jarvis_tool:gen_readme_section;;jarvis_tool:doc_commit", "pipeline", "M1,M2"),
        ("devops_ci_pipeline", "pipeline ci complet", "jarvis_tool:lint_fix;;sleep:2;;jarvis_tool:test_suite;;sleep:10;;jarvis_tool:security_scan;;sleep:5;;jarvis_tool:build_electron;;sleep:15;;jarvis_tool:deploy_staging", "pipeline", "M1,M2,GEMINI"),
    ]
    for pid, trigger, steps, atype, agents in devops:
        pipes.append((pid, trigger, steps, "devops", atype, agents))

    # ── TRADING ADVANCED (50 pipelines) ──
    trading = [
        ("trading_full_scan", "scan complet du marche", "jarvis_tool:trading_scan;;sleep:5;;jarvis_tool:breakout_detect;;sleep:3;;jarvis_tool:rsi_analysis;;sleep:2;;jarvis_tool:trading_report", "pipeline", "OL1,M1,M2"),
        ("trading_multi_tf", "analyse multi-timeframe", "jarvis_tool:scan_1m;;jarvis_tool:scan_5m;;jarvis_tool:scan_15m;;jarvis_tool:scan_1h;;jarvis_tool:scan_4h;;sleep:3;;jarvis_tool:tf_consensus", "pipeline", "OL1,M1,M2"),
        ("trading_risk_check", "verification du risque", "jarvis_tool:portfolio_status;;sleep:1;;jarvis_tool:risk_calc;;sleep:1;;jarvis_tool:exposure_check;;jarvis_tool:risk_report", "pipeline", "M1,M2"),
        ("trading_sniper_cycle", "cycle sniper complet", "jarvis_tool:scan_breakout;;sleep:2;;jarvis_tool:validate_signal M1;;sleep:1;;jarvis_tool:validate_signal M2;;sleep:1;;jarvis_tool:consensus_signal;;jarvis_tool:execute_trade", "pipeline", "OL1,M1,M2,M3"),
        ("trading_portfolio_rebalance", "reequilibre le portfolio", "jarvis_tool:portfolio_status;;sleep:1;;jarvis_tool:market_conditions;;sleep:2;;jarvis_tool:calc_rebalance;;sleep:1;;jarvis_tool:execute_rebalance", "pipeline", "M1,M2,OL1"),
        ("trading_backtest_cycle", "backteste une strategie", "jarvis_tool:load_strategy;;sleep:1;;jarvis_tool:fetch_historical;;sleep:5;;jarvis_tool:run_backtest;;sleep:10;;jarvis_tool:backtest_report", "pipeline", "M1,M2"),
        ("trading_sentiment_scan", "analyse de sentiment", "jarvis_tool:web_search crypto sentiment;;sleep:3;;jarvis_tool:analyze_sentiment M1;;sleep:2;;jarvis_tool:sentiment_score;;jarvis_tool:sentiment_report", "pipeline", "OL1,M1,GEMINI"),
        ("trading_liquidation_alert", "alerte de liquidation", "jarvis_tool:check_positions;;sleep:1;;jarvis_tool:calc_liq_price;;sleep:1;;jarvis_tool:set_sl_protection;;jarvis_tool:alert_notify", "pipeline", "M1,OL1"),
        ("trading_daily_pnl", "pnl quotidien", "jarvis_tool:fetch_trades_today;;sleep:2;;jarvis_tool:calc_pnl;;sleep:1;;jarvis_tool:pnl_report;;jarvis_tool:save_pnl_db", "pipeline", "M1,M2"),
        ("trading_correlation_map", "carte de correlation", "jarvis_tool:fetch_prices BTC ETH SOL;;sleep:3;;jarvis_tool:calc_correlation;;sleep:2;;jarvis_tool:correlation_report", "pipeline", "M1,M2"),
        ("trading_whale_watch", "surveillance des whales", "jarvis_tool:web_search whale alert;;sleep:3;;jarvis_tool:analyze_whale_data;;sleep:2;;jarvis_tool:whale_report", "pipeline", "OL1,M1"),
        ("trading_funding_rate", "analyse funding rate", "jarvis_tool:fetch_funding_rates;;sleep:2;;jarvis_tool:analyze_funding;;sleep:1;;jarvis_tool:funding_signal", "pipeline", "OL1,M1"),
        ("trading_volume_profile", "profil de volume", "jarvis_tool:fetch_volume_data;;sleep:3;;jarvis_tool:calc_vwap;;sleep:1;;jarvis_tool:volume_report", "pipeline", "M1,M2"),
        ("trading_exit_strategy", "strategie de sortie", "jarvis_tool:check_positions;;sleep:1;;jarvis_tool:calc_tp_levels;;sleep:1;;jarvis_tool:set_trailing_stop;;jarvis_tool:exit_plan_report", "pipeline", "M1,M2"),
        ("trading_morning_brief", "brief trading du matin", "jarvis_tool:overnight_recap;;sleep:2;;jarvis_tool:market_conditions;;sleep:2;;jarvis_tool:top_movers;;sleep:1;;jarvis_tool:trading_plan_today", "pipeline", "OL1,M1,M2"),
        ("trading_evening_review", "revue trading du soir", "jarvis_tool:daily_pnl;;sleep:2;;jarvis_tool:trade_analysis;;sleep:3;;jarvis_tool:lessons_learned;;jarvis_tool:save_journal", "pipeline", "M1,M2,GEMINI"),
        ("trading_strategy_consensus", "consensus strategie multi-ia", "jarvis_tool:analyze M1 BTC;;jarvis_tool:analyze M2 BTC;;jarvis_tool:analyze OL1 BTC;;jarvis_tool:analyze GEMINI BTC;;sleep:5;;jarvis_tool:strategy_vote", "pipeline", "M1,M2,OL1,GEMINI"),
    ]
    for pid, trigger, steps, atype, agents in trading:
        pipes.append((pid, trigger, steps, "trading_adv", atype, agents))

    # ── AI RESEARCH (40 pipelines) ──
    ai_research = [
        ("ai_model_compare", "compare les modeles ia", "jarvis_tool:bench_node M1;;jarvis_tool:bench_node M2;;jarvis_tool:bench_node M3;;jarvis_tool:bench_node OL1;;sleep:5;;jarvis_tool:model_compare_report", "pipeline", "M1,M2,M3,OL1"),
        ("ai_prompt_optimize", "optimise les prompts", "jarvis_tool:test_prompt v1;;sleep:3;;jarvis_tool:test_prompt v2;;sleep:3;;jarvis_tool:compare_results;;jarvis_tool:select_best", "pipeline", "M1,M2"),
        ("ai_finetune_prep", "prepare le fine-tuning", "jarvis_tool:export_training_data;;sleep:2;;jarvis_tool:validate_format;;sleep:1;;jarvis_tool:split_dataset;;jarvis_tool:finetune_config", "pipeline", "M1"),
        ("ai_eval_suite", "suite d'evaluation complete", "jarvis_tool:eval_code M1;;jarvis_tool:eval_code M2;;jarvis_tool:eval_logic M1;;jarvis_tool:eval_logic OL1;;jarvis_tool:eval_math M1;;sleep:5;;jarvis_tool:eval_report", "pipeline", "M1,M2,OL1"),
        ("ai_consensus_calibrate", "calibre le consensus", "jarvis_tool:consensus_test simple;;sleep:3;;jarvis_tool:consensus_test complex;;sleep:5;;jarvis_tool:adjust_weights;;jarvis_tool:save_calibration", "pipeline", "M1,M2,M3,OL1,GEMINI"),
        ("ai_autolearn_cycle", "cycle autolearn complet", "jarvis_tool:autolearn_status;;sleep:1;;jarvis_tool:trigger_tuning;;sleep:300;;jarvis_tool:autolearn_scores;;jarvis_tool:save_tuning_results", "pipeline", "M1,M2,M3,OL1"),
        ("ai_improve_loop_run", "lance la boucle d'amelioration", "jarvis_tool:improve_loop 10;;sleep:60;;jarvis_tool:improve_results;;jarvis_tool:apply_improvements", "pipeline", "M1,M2"),
        ("ai_arena_battle", "bataille arena entre modeles", "jarvis_tool:arena_match M1 M2;;sleep:5;;jarvis_tool:arena_match M1 OL1;;sleep:5;;jarvis_tool:arena_match M2 M3;;sleep:5;;jarvis_tool:arena_ranking", "pipeline", "M1,M2,M3,OL1"),
        ("ai_embedding_test", "teste les embeddings", "jarvis_tool:embed_test M1;;sleep:3;;jarvis_tool:similarity_check;;jarvis_tool:embedding_report", "pipeline", "M1"),
        ("ai_rag_pipeline", "pipeline rag complet", "jarvis_tool:index_documents;;sleep:5;;jarvis_tool:embed_queries;;sleep:3;;jarvis_tool:retrieve_test;;sleep:2;;jarvis_tool:rag_quality_report", "pipeline", "M1,M2"),
        ("ai_multi_agent_test", "teste le multi-agent", "jarvis_tool:spawn_agents 4;;sleep:2;;jarvis_tool:assign_tasks;;sleep:10;;jarvis_tool:collect_results;;jarvis_tool:agent_perf_report", "pipeline", "M1,M2,M3,OL1"),
        ("ai_hallucination_check", "detecte les hallucinations", "jarvis_tool:gen_factual_qa;;sleep:2;;jarvis_tool:test_accuracy M1;;jarvis_tool:test_accuracy M2;;jarvis_tool:test_accuracy M3;;jarvis_tool:hallucination_report", "pipeline", "M1,M2,M3"),
        ("ai_context_window_test", "teste les fenetres de contexte", "jarvis_tool:gen_long_prompt 1k;;jarvis_tool:gen_long_prompt 4k;;jarvis_tool:gen_long_prompt 8k;;sleep:5;;jarvis_tool:context_report", "pipeline", "M1,M2"),
        ("ai_speed_benchmark", "benchmark de vitesse", "jarvis_tool:speed_test M1 100;;jarvis_tool:speed_test M2 100;;jarvis_tool:speed_test M3 100;;jarvis_tool:speed_test OL1 100;;sleep:5;;jarvis_tool:speed_report", "pipeline", "M1,M2,M3,OL1"),
        ("ai_quality_audit", "audit qualite ia", "jarvis_tool:sample_conversations 50;;sleep:2;;jarvis_tool:score_quality M2;;sleep:5;;jarvis_tool:score_quality GEMINI;;sleep:5;;jarvis_tool:quality_audit_report", "pipeline", "M2,GEMINI"),
    ]
    for pid, trigger, steps, atype, agents in ai_research:
        pipes.append((pid, trigger, steps, "ai_research", atype, agents))

    # ── SECURITY & AUDIT (40 pipelines) ──
    security = [
        ("sec_full_audit", "audit securite complet", "jarvis_tool:system_audit;;sleep:5;;jarvis_tool:network_scan;;sleep:3;;jarvis_tool:port_check;;sleep:2;;jarvis_tool:audit_report", "pipeline", "M1,GEMINI"),
        ("sec_port_scan", "scan des ports ouverts", "powershell:netstat -ano | findstr LISTENING;;sleep:1;;jarvis_tool:analyze_ports M1;;jarvis_tool:port_report", "pipeline", "M1"),
        ("sec_firewall_check", "verifie le firewall", "powershell:Get-NetFirewallProfile | Format-Table;;sleep:1;;powershell:Get-NetFirewallRule -Enabled True | Measure-Object;;jarvis_tool:firewall_report", "pipeline", "M1"),
        ("sec_process_audit", "audit des processus", "powershell:Get-Process | Sort-Object CPU -Descending | Select-Object -First 20;;sleep:1;;jarvis_tool:process_analysis;;jarvis_tool:process_report", "pipeline", "M1,M2"),
        ("sec_credential_check", "verifie les credentials", "jarvis_tool:scan_env_files;;sleep:1;;jarvis_tool:check_api_keys;;sleep:1;;jarvis_tool:credential_report", "pipeline", "M1,GEMINI"),
        ("sec_network_monitor", "moniteur reseau", "powershell:Get-NetTCPConnection | Where-Object State -eq Established;;sleep:1;;jarvis_tool:connection_analysis;;jarvis_tool:network_report", "pipeline", "M1"),
        ("sec_update_check", "verifie les mises a jour", "powershell:winget upgrade --include-unknown;;sleep:3;;jarvis_tool:update_analysis;;jarvis_tool:update_report", "pipeline", "M1"),
        ("sec_backup_verify", "verifie les sauvegardes", "jarvis_tool:list_backups;;sleep:1;;jarvis_tool:verify_integrity;;sleep:2;;jarvis_tool:backup_report", "pipeline", "M1"),
        ("sec_ssl_check", "verifie les certificats ssl", "jarvis_tool:check_ssl_certs;;sleep:2;;jarvis_tool:ssl_report", "pipeline", "M1,OL1"),
        ("sec_disk_encrypt_status", "statut chiffrement disques", "powershell:manage-bde -status;;sleep:1;;jarvis_tool:encryption_report", "pipeline", "M1"),
        ("sec_event_log_scan", "scan des logs windows", "powershell:Get-EventLog -LogName Security -Newest 50 | Format-Table;;sleep:2;;jarvis_tool:log_analysis M1;;jarvis_tool:security_log_report", "pipeline", "M1,M2"),
        ("sec_vulnerability_scan", "scan de vulnerabilites", "jarvis_tool:dep_audit;;sleep:2;;jarvis_tool:code_scan;;sleep:3;;jarvis_tool:vuln_report", "pipeline", "M1,GEMINI"),
    ]
    for pid, trigger, steps, atype, agents in security:
        pipes.append((pid, trigger, steps, "security", atype, agents))

    # ── DATA ENGINEERING (35 pipelines) ──
    data_eng = [
        ("data_backup_full", "backup complet des bases", "jarvis_tool:backup_db etoile;;sleep:2;;jarvis_tool:backup_db jarvis;;sleep:2;;jarvis_tool:backup_db trading;;sleep:2;;jarvis_tool:backup_report", "pipeline", "M1"),
        ("data_db_optimize", "optimise les bases de donnees", "jarvis_tool:vacuum_db etoile;;sleep:3;;jarvis_tool:vacuum_db jarvis;;sleep:3;;jarvis_tool:analyze_db;;jarvis_tool:db_stats", "pipeline", "M1"),
        ("data_export_json", "exporte les donnees en json", "jarvis_tool:export_pipelines;;sleep:1;;jarvis_tool:export_scenarios;;sleep:1;;jarvis_tool:export_commands;;jarvis_tool:export_report", "pipeline", "M1"),
        ("data_integrity_check", "verifie l'integrite des donnees", "jarvis_tool:check_foreign_keys;;sleep:1;;jarvis_tool:check_duplicates;;sleep:1;;jarvis_tool:check_orphans;;jarvis_tool:integrity_report", "pipeline", "M1"),
        ("data_stats_dashboard", "genere le dashboard de stats", "jarvis_tool:count_all_tables;;sleep:1;;jarvis_tool:usage_stats;;sleep:1;;jarvis_tool:trend_analysis;;jarvis_tool:dashboard_update", "pipeline", "M1,M2"),
        ("data_clean_old_logs", "nettoie les vieux logs", "jarvis_tool:archive_logs 30d;;sleep:2;;jarvis_tool:clean_tool_log;;sleep:1;;jarvis_tool:clean_metrics 90d;;jarvis_tool:cleanup_report", "pipeline", "M1"),
        ("data_sync_dbs", "synchronise les bases entre machines", "jarvis_tool:export_db_diff;;sleep:2;;jarvis_tool:sync_to_m2;;sleep:3;;jarvis_tool:sync_to_m3;;sleep:3;;jarvis_tool:sync_verify", "pipeline", "M1,M2,M3"),
        ("data_benchmark_archive", "archive les resultats de benchmark", "jarvis_tool:collect_benchmarks;;sleep:1;;jarvis_tool:compress_old;;sleep:2;;jarvis_tool:index_archive;;jarvis_tool:archive_report", "pipeline", "M1"),
        ("data_pipeline_stats", "statistiques d'usage des pipelines", "jarvis_tool:pipeline_usage_report;;sleep:2;;jarvis_tool:top_pipelines;;sleep:1;;jarvis_tool:unused_pipelines;;jarvis_tool:pipeline_stats_report", "pipeline", "M1,M2"),
        ("data_scenario_validation", "validation des scenarios", "jarvis_tool:run_validation_cycle;;sleep:30;;jarvis_tool:validation_report;;jarvis_tool:fix_failed_scenarios", "pipeline", "M1,M2,M3"),
    ]
    for pid, trigger, steps, atype, agents in data_eng:
        pipes.append((pid, trigger, steps, "data_eng", atype, agents))

    # ── MONITORING (35 pipelines) ──
    monitoring = [
        ("mon_system_health", "sante systeme complete", "powershell:Get-CimInstance Win32_Processor | Select LoadPercentage;;powershell:Get-CimInstance Win32_OperatingSystem | Select FreePhysicalMemory;;jarvis_tool:gpu_status;;jarvis_tool:disk_space;;jarvis_tool:system_health_report", "pipeline", "M1"),
        ("mon_gpu_thermal_loop", "boucle thermique gpu", "jarvis_tool:thermal_check;;sleep:5;;jarvis_tool:thermal_check;;sleep:5;;jarvis_tool:thermal_check;;jarvis_tool:thermal_trend", "pipeline", "M1,M2,M3"),
        ("mon_network_latency", "latence reseau du cluster", "powershell:Test-Connection 10.5.0.2 -Count 5;;powershell:Test-Connection 192.168.1.26 -Count 5;;powershell:Test-Connection 192.168.1.113 -Count 5;;jarvis_tool:latency_report", "pipeline", "M1,M2,M3"),
        ("mon_disk_usage", "utilisation des disques", "powershell:Get-PSDrive -PSProvider FileSystem | Select Name, @{n='Free(GB)';e={[math]::Round($_.Free/1GB,1)}}, @{n='Used(GB)';e={[math]::Round($_.Used/1GB,1)}};;jarvis_tool:disk_report", "pipeline", "M1"),
        ("mon_process_top", "top processus par ressources", "powershell:Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Name, @{n='MB';e={[math]::Round($_.WorkingSet64/1MB)}};;jarvis_tool:process_report", "pipeline", "M1"),
        ("mon_ollama_health", "sante ollama", "powershell:curl -s http://127.0.0.1:11434/api/tags;;sleep:1;;jarvis_tool:ollama_model_check;;jarvis_tool:ollama_report", "pipeline", "OL1"),
        ("mon_lmstudio_health", "sante lm studio", "jarvis_tool:lms_models M1;;jarvis_tool:lms_models M2;;jarvis_tool:lms_models M3;;jarvis_tool:lmstudio_report", "pipeline", "M1,M2,M3"),
        ("mon_service_check", "verification des services", "jarvis_tool:check_port 1234 M1;;jarvis_tool:check_port 1234 M2;;jarvis_tool:check_port 1234 M3;;jarvis_tool:check_port 11434 OL1;;jarvis_tool:check_port 18800 canvas;;jarvis_tool:service_report", "pipeline", "M1,M2,M3,OL1"),
        ("mon_api_health", "sante des api", "jarvis_tool:ping_api M1;;jarvis_tool:ping_api M2;;jarvis_tool:ping_api M3;;jarvis_tool:ping_api OL1;;jarvis_tool:ping_api GEMINI;;jarvis_tool:api_health_report", "pipeline", "M1,M2,M3,OL1,GEMINI"),
        ("mon_memory_pressure", "pression memoire", "powershell:Get-Counter '\\Memory\\Available MBytes';;powershell:Get-Counter '\\Memory\\% Committed Bytes In Use';;jarvis_tool:memory_report", "pipeline", "M1"),
        ("mon_uptime_report", "rapport d'uptime", "jarvis_tool:node_uptime M1;;jarvis_tool:node_uptime M2;;jarvis_tool:node_uptime M3;;jarvis_tool:node_uptime OL1;;jarvis_tool:uptime_report", "pipeline", "M1,M2,M3,OL1"),
    ]
    for pid, trigger, steps, atype, agents in monitoring:
        pipes.append((pid, trigger, steps, "monitoring", atype, agents))

    # ── ROUTINES CYCLIQUES (40 pipelines) ──
    routines = [
        ("routine_morning_full", "routine complete du matin", "jarvis_tool:cluster_check;;sleep:2;;jarvis_tool:gpu_status;;sleep:1;;jarvis_tool:trading_morning_brief;;sleep:3;;jarvis_tool:calendar_today;;sleep:1;;jarvis_tool:weather;;jarvis_tool:morning_summary", "pipeline", "M1,M2,OL1"),
        ("routine_evening_full", "routine complete du soir", "jarvis_tool:daily_pnl;;sleep:2;;jarvis_tool:cluster_report;;sleep:2;;jarvis_tool:save_daily_stats;;sleep:1;;jarvis_tool:backup_db;;jarvis_tool:evening_summary", "pipeline", "M1,M2,OL1"),
        ("routine_work_start", "debut de session de travail", "jarvis_tool:cluster_check;;sleep:1;;app_open:code;;sleep:2;;app_open:wt;;sleep:1;;browser:navigate:https://github.com;;jarvis_tool:work_context_load", "pipeline", "M1,M2"),
        ("routine_work_end", "fin de session de travail", "jarvis_tool:git_commit_wip;;sleep:2;;jarvis_tool:save_work_context;;sleep:1;;jarvis_tool:daily_summary;;jarvis_tool:cluster_standby", "pipeline", "M1"),
        ("routine_trading_session", "session trading complete", "jarvis_tool:market_conditions;;sleep:2;;jarvis_tool:portfolio_status;;sleep:1;;jarvis_tool:scan_opportunities;;sleep:5;;jarvis_tool:risk_check;;jarvis_tool:trading_ready", "pipeline", "OL1,M1,M2"),
        ("routine_coding_session", "session coding preparee", "jarvis_tool:cluster_check;;sleep:1;;jarvis_tool:load_context;;sleep:1;;app_open:code;;app_open:wt;;jarvis_tool:code_ready", "pipeline", "M1,M2"),
        ("routine_maintenance", "maintenance hebdomadaire", "jarvis_tool:backup_full;;sleep:5;;jarvis_tool:clean_logs;;sleep:2;;jarvis_tool:vacuum_dbs;;sleep:3;;jarvis_tool:update_check;;sleep:2;;jarvis_tool:benchmark_full;;sleep:30;;jarvis_tool:maintenance_report", "pipeline", "M1,M2,M3"),
        ("routine_gaming_mode", "mode gaming active", "jarvis_tool:cluster_standby;;sleep:1;;jarvis_tool:reduce_bg_processes;;sleep:1;;jarvis_tool:gpu_gaming_mode;;jarvis_tool:gaming_ready", "pipeline", "M1"),
        ("routine_focus_mode", "mode focus sans distraction", "jarvis_tool:dnd_enable;;sleep:1;;jarvis_tool:close_social;;sleep:1;;jarvis_tool:timer_start 90;;jarvis_tool:focus_active", "pipeline", "M1"),
        ("routine_break_mode", "mode pause", "jarvis_tool:save_work_context;;sleep:1;;jarvis_tool:lock_screen;;sleep:1;;jarvis_tool:timer_start 15", "pipeline", "M1"),
        ("routine_presentation_mode", "mode presentation", "jarvis_tool:dnd_enable;;sleep:1;;jarvis_tool:close_personal;;sleep:1;;jarvis_tool:screen_setup_present;;jarvis_tool:present_ready", "pipeline", "M1"),
        ("routine_debug_session", "session de debug preparee", "jarvis_tool:cluster_check;;sleep:1;;jarvis_tool:load_error_context;;sleep:1;;app_open:code;;jarvis_tool:debug_tools_ready", "pipeline", "M1,M2,M3"),
        ("routine_review_session", "session de revue de code", "jarvis_tool:git_log_week;;sleep:1;;jarvis_tool:code_quality_scan;;sleep:3;;jarvis_tool:review_ready", "pipeline", "M1,M2,GEMINI"),
        ("routine_learning_mode", "mode apprentissage", "jarvis_tool:autolearn_status;;sleep:1;;jarvis_tool:improve_loop 5;;sleep:30;;jarvis_tool:learning_report", "pipeline", "M1,M2,M3,OL1"),
        ("routine_night_mode", "mode nuit automatique", "jarvis_tool:save_all_state;;sleep:1;;jarvis_tool:backup_db;;sleep:2;;jarvis_tool:cluster_hibernate;;sleep:1;;jarvis_tool:night_report", "pipeline", "M1"),
    ]
    for pid, trigger, steps, atype, agents in routines:
        pipes.append((pid, trigger, steps, "routine", atype, agents))

    # ── EMERGENCY (30 pipelines) ──
    emergency = [
        ("emg_node_down", "noeud en panne urgence", "jarvis_tool:identify_down_node;;sleep:1;;jarvis_tool:reroute_traffic;;sleep:1;;jarvis_tool:attempt_heal;;sleep:5;;jarvis_tool:verify_recovery;;jarvis_tool:incident_report", "pipeline", "M1,M2,M3,OL1"),
        ("emg_gpu_overheat", "surchauffe gpu urgence", "jarvis_tool:thermal_check;;sleep:1;;jarvis_tool:reduce_load;;sleep:1;;jarvis_tool:fan_max;;sleep:5;;jarvis_tool:thermal_check;;jarvis_tool:thermal_report", "pipeline", "M1,M2,M3"),
        ("emg_disk_full", "disque plein urgence", "jarvis_tool:disk_usage;;sleep:1;;jarvis_tool:clean_temp;;sleep:2;;jarvis_tool:clean_cache;;sleep:2;;jarvis_tool:disk_usage;;jarvis_tool:disk_report", "pipeline", "M1"),
        ("emg_network_down", "reseau en panne", "powershell:Test-Connection 8.8.8.8 -Count 3;;sleep:2;;powershell:ipconfig /release;;sleep:2;;powershell:ipconfig /renew;;sleep:5;;jarvis_tool:network_verify", "pipeline", "M1"),
        ("emg_ollama_crash", "ollama crash", "powershell:taskkill /f /im ollama.exe;;sleep:2;;powershell:Start-Process ollama serve;;sleep:5;;jarvis_tool:ollama_health;;jarvis_tool:recovery_report", "pipeline", "OL1"),
        ("emg_lmstudio_crash", "lm studio crash", "powershell:taskkill /f /im 'LM Studio.exe';;sleep:2;;powershell:Start-Process 'C:\\Users\\franc\\AppData\\Local\\Programs\\lm-studio\\LM Studio.exe';;sleep:10;;jarvis_tool:lmstudio_health", "pipeline", "M1"),
        ("emg_memory_critical", "memoire critique", "jarvis_tool:top_memory_procs;;sleep:1;;jarvis_tool:kill_memory_hogs;;sleep:2;;jarvis_tool:memory_status;;jarvis_tool:memory_report", "pipeline", "M1"),
        ("emg_db_corrupt", "base de donnees corrompue", "jarvis_tool:backup_db;;sleep:1;;jarvis_tool:check_db_integrity;;sleep:2;;jarvis_tool:repair_db;;sleep:3;;jarvis_tool:verify_db;;jarvis_tool:db_recovery_report", "pipeline", "M1"),
        ("emg_full_cluster_restart", "redemarrage complet du cluster", "jarvis_tool:save_all_state;;sleep:2;;jarvis_tool:shutdown_all;;sleep:10;;jarvis_tool:cold_start;;sleep:15;;jarvis_tool:cluster_check;;jarvis_tool:restart_report", "pipeline", "M1,M2,M3,OL1"),
        ("emg_trading_halt", "arret d'urgence trading", "jarvis_tool:cancel_all_orders;;sleep:1;;jarvis_tool:close_all_positions;;sleep:2;;jarvis_tool:disable_trading;;jarvis_tool:trading_halt_report", "pipeline", "M1,OL1"),
        ("emg_rollback_deploy", "rollback de deploiement", "jarvis_tool:identify_last_good;;sleep:1;;jarvis_tool:git_revert;;sleep:2;;jarvis_tool:rebuild;;sleep:10;;jarvis_tool:deploy_verify;;jarvis_tool:rollback_report", "pipeline", "M1"),
        ("emg_cascade_failover", "failover en cascade", "jarvis_tool:check_primary;;sleep:1;;jarvis_tool:promote_secondary;;sleep:2;;jarvis_tool:reroute_all;;sleep:1;;jarvis_tool:verify_failover;;jarvis_tool:failover_report", "pipeline", "M1,M2,M3"),
    ]
    for pid, trigger, steps, atype, agents in emergency:
        pipes.append((pid, trigger, steps, "emergency", atype, agents))

    # ── INTEGRATION / N8N / WEBHOOKS (30 pipelines) ──
    integration = [
        ("int_n8n_trigger_scan", "declenche le scan n8n", "jarvis_tool:n8n_trigger scan;;sleep:5;;jarvis_tool:n8n_status;;jarvis_tool:n8n_result", "pipeline", "M1,OL1"),
        ("int_n8n_trading_flow", "flow trading n8n", "jarvis_tool:n8n_trigger trading;;sleep:10;;jarvis_tool:n8n_status;;jarvis_tool:trading_result", "pipeline", "OL1,M1"),
        ("int_webhook_notify", "notification webhook", "jarvis_tool:prepare_payload;;sleep:1;;jarvis_tool:send_webhook;;jarvis_tool:confirm_delivery", "pipeline", "M1"),
        ("int_telegram_alert", "alerte telegram", "jarvis_tool:format_alert;;sleep:1;;jarvis_tool:send_telegram;;jarvis_tool:confirm_telegram", "pipeline", "M1,OL1"),
        ("int_api_chain", "chaine d'api", "jarvis_tool:call_api_1;;sleep:2;;jarvis_tool:transform_data;;sleep:1;;jarvis_tool:call_api_2;;sleep:2;;jarvis_tool:chain_report", "pipeline", "M1,M2"),
        ("int_sync_notion", "synchronise avec notion", "jarvis_tool:fetch_notion_pages;;sleep:3;;jarvis_tool:update_local_db;;sleep:2;;jarvis_tool:sync_report", "pipeline", "M1"),
        ("int_export_hf", "export vers hugging face", "jarvis_tool:prepare_dataset;;sleep:2;;jarvis_tool:validate_format;;sleep:1;;jarvis_tool:upload_hf;;sleep:5;;jarvis_tool:hf_report", "pipeline", "M1,M2"),
        ("int_github_sync", "synchronise github", "powershell:cd F:\\BUREAU\\turbo; git pull;;sleep:2;;jarvis_tool:merge_check;;sleep:1;;powershell:cd F:\\BUREAU\\turbo; git push;;jarvis_tool:github_sync_report", "pipeline", "M1"),
        ("int_canva_export", "exporte vers canva", "jarvis_tool:prepare_design_data;;sleep:1;;jarvis_tool:canva_create;;sleep:5;;jarvis_tool:canva_export;;jarvis_tool:design_report", "pipeline", "M1,GEMINI"),
        ("int_multi_platform_publish", "publie sur plusieurs plateformes", "jarvis_tool:prepare_content;;sleep:1;;jarvis_tool:publish_github;;jarvis_tool:publish_hf;;jarvis_tool:publish_telegram;;jarvis_tool:publish_report", "pipeline", "M1,OL1"),
    ]
    for pid, trigger, steps, atype, agents in integration:
        pipes.append((pid, trigger, steps, "integration", atype, agents))

    # ── OPTIMIZATION (30 pipelines) ──
    optimization = [
        ("opt_model_swap_perf", "swap modele pour performance", "jarvis_tool:bench_current;;sleep:3;;jarvis_tool:model_swap qwen3-30b;;sleep:10;;jarvis_tool:bench_new;;sleep:3;;jarvis_tool:compare_perf;;jarvis_tool:decide_keep", "pipeline", "M1"),
        ("opt_cache_tuning", "optimise le cache", "jarvis_tool:cache_stats;;sleep:1;;jarvis_tool:cache_clear_stale;;sleep:1;;jarvis_tool:cache_resize;;jarvis_tool:cache_report", "pipeline", "M1"),
        ("opt_routing_rebalance", "reequilibre le routage", "jarvis_tool:routing_stats;;sleep:1;;jarvis_tool:detect_imbalance;;sleep:1;;jarvis_tool:adjust_weights;;jarvis_tool:routing_report", "pipeline", "M1,M2"),
        ("opt_prompt_compression", "compresse les prompts", "jarvis_tool:analyze_prompt_lengths;;sleep:1;;jarvis_tool:compress_system_prompts;;sleep:2;;jarvis_tool:test_compressed;;jarvis_tool:compression_report", "pipeline", "M1,M2"),
        ("opt_batch_inference", "optimise l'inference batch", "jarvis_tool:collect_pending;;sleep:1;;jarvis_tool:batch_process;;sleep:5;;jarvis_tool:batch_report", "pipeline", "M1"),
        ("opt_memory_cleanup", "nettoie la memoire", "jarvis_tool:gc_collect;;sleep:1;;jarvis_tool:clear_old_contexts;;sleep:1;;jarvis_tool:memory_status;;jarvis_tool:cleanup_report", "pipeline", "M1"),
        ("opt_latency_minimize", "minimise la latence", "jarvis_tool:latency_profile;;sleep:2;;jarvis_tool:identify_bottleneck;;sleep:1;;jarvis_tool:apply_optimization;;jarvis_tool:latency_report", "pipeline", "M1,M2"),
        ("opt_token_budget", "optimise le budget tokens", "jarvis_tool:token_usage_report;;sleep:1;;jarvis_tool:identify_waste;;sleep:1;;jarvis_tool:trim_prompts;;jarvis_tool:token_report", "pipeline", "M1"),
        ("opt_parallel_tuning", "optimise le parallelisme", "jarvis_tool:concurrency_test 2;;jarvis_tool:concurrency_test 4;;jarvis_tool:concurrency_test 8;;sleep:5;;jarvis_tool:optimal_concurrency_report", "pipeline", "M1,M2,M3,OL1"),
        ("opt_weight_autotune", "auto-tune les poids", "jarvis_tool:collect_perf_data;;sleep:2;;jarvis_tool:calc_optimal_weights;;sleep:1;;jarvis_tool:apply_weights;;jarvis_tool:weight_report", "pipeline", "M1,M2,M3,OL1"),
    ]
    for pid, trigger, steps, atype, agents in optimization:
        pipes.append((pid, trigger, steps, "optimization", atype, agents))

    # ── MULTI-MODAL (25 pipelines) ──
    multimodal = [
        ("mm_tts_pipeline", "pipeline text to speech", "jarvis_tool:prepare_text;;sleep:1;;jarvis_tool:tts_generate;;sleep:3;;jarvis_tool:play_audio", "pipeline", "M1"),
        ("mm_stt_pipeline", "pipeline speech to text", "jarvis_tool:record_audio;;sleep:5;;jarvis_tool:whisper_transcribe;;sleep:3;;jarvis_tool:process_text", "pipeline", "M1"),
        ("mm_voice_command_cycle", "cycle commande vocale", "jarvis_tool:listen;;sleep:3;;jarvis_tool:transcribe;;sleep:1;;jarvis_tool:classify_intent;;sleep:1;;jarvis_tool:execute_command;;jarvis_tool:tts_response", "pipeline", "M1,OL1"),
        ("mm_image_analyze", "analyse d'image", "jarvis_tool:capture_screen;;sleep:1;;jarvis_tool:analyze_image GEMINI;;sleep:5;;jarvis_tool:image_report", "pipeline", "GEMINI"),
        ("mm_doc_summarize", "resume un document", "jarvis_tool:read_document;;sleep:1;;jarvis_tool:summarize M1;;sleep:3;;jarvis_tool:summarize M2;;sleep:3;;jarvis_tool:merge_summaries", "pipeline", "M1,M2"),
        ("mm_translate_pipeline", "pipeline de traduction", "jarvis_tool:detect_language;;sleep:1;;jarvis_tool:translate M1;;sleep:2;;jarvis_tool:verify_translation M2;;jarvis_tool:translation_report", "pipeline", "M1,M2"),
        ("mm_code_explain", "explique du code", "jarvis_tool:read_code;;sleep:1;;jarvis_tool:explain M1;;sleep:3;;jarvis_tool:explain M2;;sleep:3;;jarvis_tool:merge_explanations", "pipeline", "M1,M2"),
        ("mm_report_gen", "genere un rapport complet", "jarvis_tool:collect_data;;sleep:2;;jarvis_tool:analyze M1;;sleep:3;;jarvis_tool:format_report;;sleep:1;;jarvis_tool:generate_pdf", "pipeline", "M1,M2"),
    ]
    for pid, trigger, steps, atype, agents in multimodal:
        pipes.append((pid, trigger, steps, "multimodal", atype, agents))

    # ── CONSENSUS CYCLES (25 pipelines) — the "infinite scenarios" ──
    consensus_cycles = [
        ("cons_code_review_3way", "revue code 3 agents", "jarvis_tool:code_review M1;;jarvis_tool:code_review M2;;jarvis_tool:code_review M3;;sleep:5;;jarvis_tool:merge_reviews;;jarvis_tool:consensus_score", "pipeline", "M1,M2,M3"),
        ("cons_architecture_vote", "vote architecture", "jarvis_tool:propose_archi GEMINI;;sleep:5;;jarvis_tool:review_archi M1;;sleep:3;;jarvis_tool:review_archi M2;;sleep:3;;jarvis_tool:archi_vote", "pipeline", "GEMINI,M1,M2"),
        ("cons_bug_hunt", "chasse aux bugs collaborative", "jarvis_tool:analyze_bug M1;;jarvis_tool:analyze_bug M2;;jarvis_tool:analyze_bug OL1;;sleep:5;;jarvis_tool:consensus_bug;;jarvis_tool:apply_fix", "pipeline", "M1,M2,OL1"),
        ("cons_trading_signal_4way", "signal trading 4 agents", "jarvis_tool:analyze_market M1;;jarvis_tool:analyze_market M2;;jarvis_tool:analyze_market OL1;;jarvis_tool:analyze_market GEMINI;;sleep:5;;jarvis_tool:trading_consensus", "pipeline", "M1,M2,OL1,GEMINI"),
        ("cons_security_audit_multi", "audit securite multi-agent", "jarvis_tool:audit_code M1;;jarvis_tool:audit_code M2;;jarvis_tool:audit_code GEMINI;;sleep:5;;jarvis_tool:merge_audits;;jarvis_tool:security_consensus", "pipeline", "M1,M2,GEMINI"),
        ("cons_prompt_selection", "selection prompt par consensus", "jarvis_tool:test_prompt_a M1;;jarvis_tool:test_prompt_b M1;;jarvis_tool:test_prompt_a M2;;jarvis_tool:test_prompt_b M2;;sleep:3;;jarvis_tool:prompt_vote", "pipeline", "M1,M2"),
        ("cons_decision_6way", "decision 6 agents complet", "jarvis_tool:analyze M1;;jarvis_tool:analyze M2;;jarvis_tool:analyze M3;;jarvis_tool:analyze OL1;;jarvis_tool:analyze GEMINI;;jarvis_tool:analyze CLAUDE;;sleep:10;;jarvis_tool:weighted_vote", "pipeline", "M1,M2,M3,OL1,GEMINI,CLAUDE"),
        ("cons_fact_check", "verification factuelle multi-agent", "jarvis_tool:fact_check M1;;jarvis_tool:fact_check OL1;;jarvis_tool:web_verify;;sleep:3;;jarvis_tool:fact_consensus", "pipeline", "M1,OL1,GEMINI"),
        ("cons_strategy_debate", "debat strategique entre agents", "jarvis_tool:propose M1;;sleep:3;;jarvis_tool:critique M2;;sleep:3;;jarvis_tool:counter M1;;sleep:3;;jarvis_tool:judge GEMINI;;jarvis_tool:final_decision", "pipeline", "M1,M2,GEMINI"),
        ("cons_quality_gate", "porte qualite multi-agent", "jarvis_tool:check_quality M1;;jarvis_tool:check_quality M2;;jarvis_tool:check_quality M3;;sleep:3;;jarvis_tool:quality_gate_decision", "pipeline", "M1,M2,M3"),
    ]
    for pid, trigger, steps, atype, agents in consensus_cycles:
        pipes.append((pid, trigger, steps, "consensus", atype, agents))

    return pipes


# ══════════════════════════════════════════════════════════════════════════════
# 2. DOMINO CHAINS — ~150 chaines avec cycles
# ══════════════════════════════════════════════════════════════════════════════

def gen_domino_chains():
    """Generate domino chains including cyclic ones."""
    chains = []

    # ── MONITORING CYCLES (A→B→C→A) ──
    chains += [
        # Cycle thermique: thermal → alert si chaud → heal → re-check → (reboucle)
        ("thermal_check", "temp_high", "reduce_gpu_load", 0, 1, "Reduit charge GPU si temp elevee"),
        ("reduce_gpu_load", "complete", "thermal_check", 5000, 1, "Re-verifie apres reduction [CYCLE]"),
        ("thermal_check", "temp_critical", "emergency_cool", 0, 1, "Refroidissement d'urgence si critique"),
        ("emergency_cool", "complete", "thermal_check", 10000, 1, "Re-verifie apres refroidissement [CYCLE]"),
        ("thermal_check", "temp_normal", "log_thermal", 0, 1, "Log si temperature normale"),

        # Cycle monitoring: check → log → sleep → recheck
        ("system_health", "complete", "log_health_metrics", 0, 1, "Log metriques apres health check"),
        ("log_health_metrics", "complete", "system_health", 60000, 1, "Recheck sante apres 60s [CYCLE]"),

        # Cycle VRAM: check → alert → cleanup → recheck
        ("vram_check", "vram_high", "vram_cleanup", 0, 1, "Nettoie VRAM si haute"),
        ("vram_cleanup", "complete", "vram_check", 5000, 1, "Reverifie VRAM apres cleanup [CYCLE]"),
        ("vram_check", "vram_ok", "log_vram", 0, 1, "Log VRAM si ok"),
    ]

    # ── CLUSTER HEALING CYCLES ──
    chains += [
        # Cycle heal: detect → diagnose → heal → verify → report
        ("cluster_check", "node_fail", "diagnose_node", 0, 1, "Diagnostique le noeud en panne"),
        ("diagnose_node", "fixable", "auto_heal", 0, 1, "Tente la reparation automatique"),
        ("auto_heal", "success", "cluster_check", 3000, 1, "Reverifie cluster apres heal [CYCLE]"),
        ("auto_heal", "fail", "escalate_alert", 0, 1, "Escalade si heal echoue"),
        ("escalate_alert", "acknowledged", "manual_heal", 0, 0, "Attente intervention manuelle"),
        ("manual_heal", "complete", "cluster_check", 2000, 1, "Reverifie apres reparation manuelle [CYCLE]"),

        # Cycle failover: primary down → promote secondary → verify
        ("primary_check", "offline", "promote_secondary", 0, 1, "Promotion du secondaire"),
        ("promote_secondary", "complete", "verify_failover", 2000, 1, "Verifie le failover"),
        ("verify_failover", "ok", "log_failover", 0, 1, "Log le failover reussi"),
        ("verify_failover", "fail", "promote_secondary", 5000, 1, "Retente promotion [CYCLE]"),

        # Cycle model reload: detect crash → restart → reload → verify
        ("model_check", "model_unloaded", "model_reload", 0, 1, "Recharge le modele"),
        ("model_reload", "success", "model_check", 5000, 1, "Verifie apres reload [CYCLE]"),
        ("model_reload", "fail", "model_restart_service", 0, 1, "Redemarre le service LM Studio"),
        ("model_restart_service", "complete", "model_reload", 10000, 1, "Retente reload apres restart [CYCLE]"),
    ]

    # ── TRADING CYCLES ──
    chains += [
        # Cycle scan → analyze → decide → execute → monitor → rescan
        ("trading_scan", "signal_found", "analyze_signal", 0, 1, "Analyse le signal detecte"),
        ("analyze_signal", "strong", "validate_consensus", 0, 1, "Valide par consensus multi-agent"),
        ("validate_consensus", "approved", "execute_trade", 0, 1, "Execute le trade approuve"),
        ("validate_consensus", "rejected", "trading_scan", 30000, 1, "Rescan apres rejet [CYCLE]"),
        ("execute_trade", "filled", "monitor_position", 0, 1, "Monitore la position ouverte"),
        ("monitor_position", "tp_hit", "log_trade_win", 0, 1, "Log le trade gagnant"),
        ("monitor_position", "sl_hit", "log_trade_loss", 0, 1, "Log le trade perdant"),
        ("log_trade_win", "complete", "trading_scan", 60000, 1, "Rescan apres trade [CYCLE]"),
        ("log_trade_loss", "complete", "analyze_failure", 0, 1, "Analyse l'echec"),
        ("analyze_failure", "complete", "trading_scan", 120000, 1, "Rescan apres analyse [CYCLE]"),

        # Cycle risk: check → alert → reduce → recheck
        ("risk_check", "exposure_high", "reduce_exposure", 0, 1, "Reduit l'exposition"),
        ("reduce_exposure", "complete", "risk_check", 5000, 1, "Reverifie risque [CYCLE]"),
        ("risk_check", "exposure_ok", "log_risk", 0, 1, "Log risque ok"),

        # Cycle PnL: calc → report → adjust → recalc
        ("calc_pnl", "complete", "pnl_report", 0, 1, "Genere rapport PnL"),
        ("pnl_report", "loss_streak", "adjust_strategy", 0, 1, "Ajuste strategie si pertes"),
        ("adjust_strategy", "complete", "trading_scan", 30000, 1, "Rescan avec nouvelle strategie [CYCLE]"),
    ]

    # ── DEVOPS CYCLES ──
    chains += [
        # Cycle CI: push → test → review → deploy → verify
        ("git_push", "complete", "run_tests", 2000, 1, "Lance tests apres push"),
        ("run_tests", "pass", "code_review_auto", 0, 1, "Revue de code si tests passent"),
        ("run_tests", "fail", "notify_failure", 0, 1, "Notifie echec des tests"),
        ("notify_failure", "fixed", "run_tests", 2000, 1, "Relance tests apres fix [CYCLE]"),
        ("code_review_auto", "approved", "deploy_staging", 0, 1, "Deploie en staging"),
        ("deploy_staging", "complete", "verify_deploy", 5000, 1, "Verifie le deploiement"),
        ("verify_deploy", "ok", "deploy_production", 0, 0, "Attente validation pour prod"),
        ("verify_deploy", "fail", "rollback_deploy", 0, 1, "Rollback si verification echoue"),
        ("rollback_deploy", "complete", "notify_rollback", 0, 1, "Notifie le rollback"),

        # Cycle quality: scan → fix → rescan
        ("quality_scan", "issues_found", "auto_fix", 0, 1, "Corrige les problemes automatiquement"),
        ("auto_fix", "complete", "quality_scan", 3000, 1, "Rescan apres correction [CYCLE]"),
        ("quality_scan", "clean", "log_quality", 0, 1, "Log qualite parfaite"),
    ]

    # ── AI RESEARCH CYCLES ──
    chains += [
        # Cycle benchmark: run → analyze → tune → rerun
        ("benchmark_run", "complete", "analyze_results", 0, 1, "Analyse les resultats du benchmark"),
        ("analyze_results", "needs_tuning", "tune_parameters", 0, 1, "Ajuste les parametres"),
        ("tune_parameters", "complete", "benchmark_run", 5000, 1, "Relance benchmark apres tuning [CYCLE]"),
        ("analyze_results", "optimal", "save_config", 0, 1, "Sauvegarde config optimale"),

        # Cycle autolearn: tune → evaluate → adjust → retune
        ("autolearn_tune", "complete", "evaluate_quality", 0, 1, "Evalue la qualite apres tuning"),
        ("evaluate_quality", "degraded", "rollback_tuning", 0, 1, "Rollback si qualite degradee"),
        ("rollback_tuning", "complete", "autolearn_tune", 60000, 1, "Retune apres rollback [CYCLE]"),
        ("evaluate_quality", "improved", "save_tuning", 0, 1, "Sauvegarde tuning reussi"),

        # Cycle improve: test → score → improve → retest
        ("improve_test", "low_score", "improve_prompt", 0, 1, "Ameliore le prompt si score bas"),
        ("improve_prompt", "complete", "improve_test", 2000, 1, "Reteste avec prompt ameliore [CYCLE]"),
        ("improve_test", "high_score", "save_improvement", 0, 1, "Sauvegarde amelioration"),

        # Cycle arena: match → score → rank → rematch
        ("arena_match", "complete", "update_ranking", 0, 1, "Met a jour le classement"),
        ("update_ranking", "new_champion", "export_champion_config", 0, 1, "Exporte config du champion"),
        ("update_ranking", "no_change", "arena_match", 30000, 1, "Nouveau match si pas de changement [CYCLE]"),
    ]

    # ── ROUTINE CYCLES ──
    chains += [
        # Cycle routine matin: check → brief → prepare → ready
        ("routine_matin", "start", "cluster_health_full", 0, 1, "Health check au demarrage"),
        ("cluster_health_full", "all_ok", "morning_brief", 2000, 1, "Brief si tout va bien"),
        ("cluster_health_full", "issues", "cluster_heal_auto", 0, 1, "Heal si problemes"),
        ("morning_brief", "complete", "load_work_context", 0, 1, "Charge le contexte de travail"),

        # Cycle routine soir: save → backup → report → sleep
        ("routine_soir", "start", "save_all_state", 0, 1, "Sauvegarde tout l'etat"),
        ("save_all_state", "complete", "backup_databases", 2000, 1, "Backup des bases"),
        ("backup_databases", "complete", "generate_daily_report", 0, 1, "Genere rapport quotidien"),
        ("generate_daily_report", "complete", "cluster_standby", 5000, 1, "Met cluster en standby"),

        # Cycle maintenance: backup → clean → optimize → verify
        ("maintenance_start", "start", "backup_full", 0, 1, "Backup complet en debut de maintenance"),
        ("backup_full", "complete", "clean_all_logs", 2000, 1, "Nettoie tous les logs"),
        ("clean_all_logs", "complete", "vacuum_all_dbs", 0, 1, "Vacuum toutes les BDD"),
        ("vacuum_all_dbs", "complete", "run_benchmark", 3000, 1, "Benchmark apres maintenance"),
        ("run_benchmark", "complete", "maintenance_report", 0, 1, "Rapport de maintenance"),
    ]

    # ── EMERGENCY CYCLES ──
    chains += [
        # Cycle cascade recovery: detect → isolate → recover → integrate → verify
        ("cascade_detect", "multiple_failures", "isolate_healthy", 0, 1, "Isole les noeuds sains"),
        ("isolate_healthy", "complete", "recover_failed", 0, 1, "Tente recuperation des noeuds"),
        ("recover_failed", "partial", "verify_minimum_viable", 0, 1, "Verifie config minimale"),
        ("recover_failed", "complete", "integrate_all", 2000, 1, "Reintegre tous les noeuds"),
        ("integrate_all", "complete", "cascade_detect", 10000, 1, "Surveille apres integration [CYCLE]"),
        ("verify_minimum_viable", "ok", "continue_degraded", 0, 1, "Continue en mode degrade"),
        ("verify_minimum_viable", "fail", "full_cluster_restart", 0, 1, "Restart complet si echec"),

        # Cycle watchdog: heartbeat → miss → alert → check → heartbeat
        ("heartbeat_check", "miss", "node_alert", 0, 1, "Alerte si heartbeat manque"),
        ("node_alert", "responded", "heartbeat_check", 10000, 1, "Reprend monitoring [CYCLE]"),
        ("node_alert", "no_response", "force_restart_node", 0, 1, "Force restart du noeud"),
        ("force_restart_node", "complete", "heartbeat_check", 15000, 1, "Reprend monitoring apres restart [CYCLE]"),
    ]

    # ── CONSENSUS CYCLES ──
    chains += [
        # Cycle consensus: query → vote → disagree → re-query → re-vote
        ("consensus_query", "complete", "consensus_vote", 0, 1, "Vote apres queries paralleles"),
        ("consensus_vote", "agreement", "consensus_accept", 0, 1, "Accepte si accord"),
        ("consensus_vote", "disagreement", "consensus_clarify", 0, 1, "Clarifie si desaccord"),
        ("consensus_clarify", "complete", "consensus_query", 2000, 1, "Re-query apres clarification [CYCLE]"),

        # Cycle quality gate: check → gate → fix → recheck
        ("quality_gate_check", "pass", "deploy_approved", 0, 1, "Deploiement approuve"),
        ("quality_gate_check", "fail", "quality_fix", 0, 1, "Correction qualite"),
        ("quality_fix", "complete", "quality_gate_check", 2000, 1, "Re-check apres correction [CYCLE]"),
    ]

    # ── DATA CYCLES ──
    chains += [
        # Cycle ETL: extract → transform → load → verify → schedule next
        ("data_extract", "complete", "data_transform", 0, 1, "Transforme les donnees extraites"),
        ("data_transform", "complete", "data_load", 0, 1, "Charge les donnees transformees"),
        ("data_load", "complete", "data_verify", 2000, 1, "Verifie les donnees chargees"),
        ("data_verify", "ok", "schedule_next_etl", 0, 1, "Programme le prochain ETL"),
        ("data_verify", "error", "data_rollback", 0, 1, "Rollback si erreur"),
        ("data_rollback", "complete", "data_extract", 5000, 1, "Retente extraction [CYCLE]"),
        ("schedule_next_etl", "trigger", "data_extract", 3600000, 1, "Prochain ETL dans 1h [CYCLE]"),
    ]

    return chains


# ══════════════════════════════════════════════════════════════════════════════
# 3. SCENARIO WEIGHTS — ~80 nouveaux scenarios de routage
# ══════════════════════════════════════════════════════════════════════════════

def gen_scenario_weights():
    """Generate new scenario weights for the new pipeline domains."""
    weights = []

    # Format: (scenario, agent, weight, priority, chain_next, description)
    scenarios = {
        "cluster_ops": [
            ("M1", 1.8, 1, "M2", "Cluster ops -> M1 prioritaire"),
            ("M2", 1.4, 2, "M3", "Cluster ops -> M2 fallback"),
            ("M3", 1.0, 3, "OL1", "Cluster ops -> M3 fallback"),
            ("OL1", 1.3, 4, None, "Cluster ops -> OL1 monitoring"),
        ],
        "devops": [
            ("M1", 1.8, 1, "M2", "DevOps -> M1 execution"),
            ("M2", 1.4, 2, "GEMINI", "DevOps -> M2 review"),
            ("GEMINI", 1.2, 3, None, "DevOps -> GEMINI architecture"),
        ],
        "trading_analysis": [
            ("OL1", 1.5, 1, "M1", "Trading analysis -> OL1 web data"),
            ("M1", 1.8, 2, "M2", "Trading analysis -> M1 compute"),
            ("M2", 1.4, 3, None, "Trading analysis -> M2 validation"),
        ],
        "ai_eval": [
            ("M1", 1.8, 1, "M2", "AI eval -> M1 primary"),
            ("M2", 1.4, 2, "M3", "AI eval -> M2 secondary"),
            ("M3", 1.0, 3, "OL1", "AI eval -> M3 tertiary"),
            ("OL1", 1.3, 4, None, "AI eval -> OL1 speed test"),
        ],
        "security_audit": [
            ("M1", 1.8, 1, "GEMINI", "Security -> M1 system scan"),
            ("GEMINI", 1.2, 2, "M2", "Security -> GEMINI analysis"),
            ("M2", 1.4, 3, None, "Security -> M2 code scan"),
        ],
        "data_pipeline": [
            ("M1", 1.8, 1, "M2", "Data pipeline -> M1 primary"),
            ("M2", 1.4, 2, None, "Data pipeline -> M2 backup"),
        ],
        "monitoring": [
            ("M1", 1.8, 1, "M2", "Monitoring -> M1 primary"),
            ("M2", 1.4, 2, "M3", "Monitoring -> M2 secondary"),
            ("M3", 1.0, 3, "OL1", "Monitoring -> M3 tertiary"),
            ("OL1", 1.3, 4, None, "Monitoring -> OL1 ollama check"),
        ],
        "emergency": [
            ("M1", 1.8, 1, "M2", "Emergency -> M1 primary response"),
            ("M2", 1.4, 2, "M3", "Emergency -> M2 secondary"),
            ("M3", 1.0, 3, "OL1", "Emergency -> M3 fallback"),
            ("OL1", 1.3, 4, None, "Emergency -> OL1 last resort"),
        ],
        "routine": [
            ("M1", 1.8, 1, "OL1", "Routine -> M1 orchestration"),
            ("OL1", 1.3, 2, "M2", "Routine -> OL1 quick tasks"),
            ("M2", 1.4, 3, None, "Routine -> M2 heavy tasks"),
        ],
        "consensus_multi": [
            ("M1", 1.8, 1, "M2", "Consensus multi -> M1 primary"),
            ("M2", 1.4, 2, "OL1", "Consensus multi -> M2"),
            ("OL1", 1.3, 3, "M3", "Consensus multi -> OL1"),
            ("M3", 1.0, 4, "GEMINI", "Consensus multi -> M3"),
            ("GEMINI", 1.2, 5, "CLAUDE", "Consensus multi -> GEMINI"),
            ("CLAUDE", 1.2, 6, None, "Consensus multi -> CLAUDE final"),
        ],
        "optimization": [
            ("M1", 1.8, 1, "M2", "Optimization -> M1 primary"),
            ("M2", 1.4, 2, None, "Optimization -> M2 validation"),
        ],
        "multimodal": [
            ("M1", 1.8, 1, "GEMINI", "Multimodal -> M1 processing"),
            ("GEMINI", 1.2, 2, "M2", "Multimodal -> GEMINI vision"),
            ("M2", 1.4, 3, None, "Multimodal -> M2 fallback"),
        ],
        "integration": [
            ("M1", 1.8, 1, "OL1", "Integration -> M1 orchestration"),
            ("OL1", 1.3, 2, "M2", "Integration -> OL1 web"),
            ("M2", 1.4, 3, None, "Integration -> M2 processing"),
        ],
        "benchmark": [
            ("M1", 1.8, 1, "M2", "Benchmark -> M1 primary"),
            ("M2", 1.4, 2, "M3", "Benchmark -> M2 secondary"),
            ("M3", 1.0, 3, "OL1", "Benchmark -> M3 tertiary"),
            ("OL1", 1.3, 4, None, "Benchmark -> OL1 speed"),
        ],
        "finetune": [
            ("M1", 1.8, 1, "M2", "Finetune -> M1 GPU primary"),
            ("M2", 1.4, 2, None, "Finetune -> M2 GPU secondary"),
        ],
        "reporting": [
            ("M1", 1.8, 1, "M2", "Reporting -> M1 generation"),
            ("M2", 1.4, 2, "GEMINI", "Reporting -> M2 formatting"),
            ("GEMINI", 1.2, 3, None, "Reporting -> GEMINI analysis"),
        ],
    }

    for scenario, agents in scenarios.items():
        for agent, weight, priority, chain_next, desc in agents:
            weights.append((scenario, agent, weight, priority, chain_next, desc))

    return weights


# ══════════════════════════════════════════════════════════════════════════════
# 4. SCENARIOS DE VALIDATION — ~300 pour jarvis.db
# ══════════════════════════════════════════════════════════════════════════════

def gen_scenarios():
    """Generate validation scenarios for jarvis.db."""
    scenarios = []

    # Helper to generate scenarios from pipeline definitions
    scenario_templates = [
        # Cluster ops
        ("cluster_health_check", "Verifier la sante du cluster", "cluster_ops", "diagnostic du cluster", '["cluster_health_full"]', "Health check complet des 4 noeuds", "normal"),
        ("cluster_auto_heal", "Reparation automatique du cluster", "cluster_ops", "repare le cluster", '["cluster_heal_auto"]', "Diagnostic + heal + verification", "normal"),
        ("cluster_bench", "Benchmark du cluster", "cluster_ops", "benchmark le cluster", '["cluster_benchmark_cycle"]', "Benchmark complet avec scores", "normal"),
        ("cluster_thermal", "Surveillance thermique", "cluster_ops", "surveille les temperatures", '["cluster_thermal_monitor"]', "Check thermique de tous les GPU", "easy"),
        ("cluster_models", "Recharger les modeles", "cluster_ops", "recharge les modeles", '["cluster_model_reload"]', "Unload + reload modeles", "normal"),
        ("cluster_failover", "Test de failover", "cluster_ops", "teste le failover", '["cluster_failover_drill"]', "Simulation panne + recovery", "hard"),
        ("cluster_cold", "Demarrage a froid", "cluster_ops", "demarre le cluster", '["cluster_cold_start"]', "Wake + check + load modeles", "hard"),
        ("cluster_shutdown", "Arret propre", "cluster_ops", "arrete le cluster", '["cluster_graceful_shutdown"]', "Save + unload + notify", "normal"),
        ("cluster_network", "Diagnostic reseau", "cluster_ops", "diagnostic reseau", '["cluster_network_diag"]', "Ping toutes les machines", "easy"),
        ("cluster_perf", "Baseline performance", "cluster_ops", "baseline de performance", '["cluster_perf_baseline"]', "Bench rapide tous noeuds", "normal"),

        # DevOps
        ("devops_push", "Commit et push", "devops", "commit et push", '["devops_git_push_cycle"]', "Git add + commit + push", "easy"),
        ("devops_test", "Lance les tests", "devops", "lance les tests", '["devops_test_suite"]', "pytest + rapport", "normal"),
        ("devops_lint", "Lint le code", "devops", "lint le code", '["devops_lint_fix"]', "ruff check + fix", "easy"),
        ("devops_docker", "Deploy docker", "devops", "deploie avec docker", '["devops_docker_deploy"]', "Build + up + status", "normal"),
        ("devops_electron", "Build electron", "devops", "compile electron", '["devops_build_electron"]', "npm run build", "hard"),
        ("devops_deps", "Update deps", "devops", "mets a jour les dependances", '["devops_update_deps"]', "uv sync + npm update", "normal"),
        ("devops_review", "Revue de code", "devops", "revue de code", '["devops_code_review_cycle"]', "Git diff + review multi-agent", "normal"),
        ("devops_security", "Scan securite", "devops", "scan de securite", '["devops_security_scan"]', "Bandit + rapport", "normal"),
        ("devops_release", "Release complete", "devops", "fais une release", '["devops_release_cycle"]', "Test + lint + build + tag + deploy", "hard"),
        ("devops_ci", "CI pipeline", "devops", "pipeline ci", '["devops_ci_pipeline"]', "Lint + test + security + build + deploy", "hard"),

        # Trading
        ("trading_full", "Scan complet marche", "trading", "scan complet du marche", '["trading_full_scan"]', "Scan + breakout + RSI + rapport", "normal"),
        ("trading_multi_tf_check", "Analyse multi-timeframe", "trading", "analyse multi-timeframe", '["trading_multi_tf"]', "Scan 1m/5m/15m/1h/4h + consensus", "hard"),
        ("trading_risk", "Check risque", "trading", "verifie le risque", '["trading_risk_check"]', "Portfolio + risk calc + exposure", "normal"),
        ("trading_sniper", "Cycle sniper", "trading", "lance le sniper", '["trading_sniper_cycle"]', "Scan + validate + consensus + execute", "hard"),
        ("trading_backtest", "Backtest strategie", "trading", "backteste la strategie", '["trading_backtest_cycle"]', "Load + fetch + run + rapport", "hard"),
        ("trading_sentiment", "Analyse sentiment", "trading", "analyse le sentiment", '["trading_sentiment_scan"]', "Web search + analyse + score", "normal"),
        ("trading_pnl", "PnL quotidien", "trading", "pnl du jour", '["trading_daily_pnl"]', "Fetch trades + calc + rapport", "easy"),
        ("trading_morning", "Brief trading matin", "trading", "brief trading", '["trading_morning_brief"]', "Overnight + conditions + movers + plan", "normal"),
        ("trading_evening", "Revue trading soir", "trading", "revue trading du soir", '["trading_evening_review"]', "PnL + analyse + lessons + journal", "normal"),
        ("trading_consensus_4", "Consensus trading 4 agents", "trading", "consensus trading", '["trading_strategy_consensus"]', "4 agents analysent + vote", "hard"),

        # AI Research
        ("ai_compare", "Compare modeles", "ai_research", "compare les modeles", '["ai_model_compare"]', "Bench tous noeuds + rapport", "normal"),
        ("ai_prompt_opt", "Optimise prompts", "ai_research", "optimise les prompts", '["ai_prompt_optimize"]', "Test v1/v2 + compare + select", "normal"),
        ("ai_eval", "Suite evaluation", "ai_research", "evaluation complete", '["ai_eval_suite"]', "Code + logique + math + rapport", "hard"),
        ("ai_autolearn", "Cycle autolearn", "ai_research", "lance l'autolearn", '["ai_autolearn_cycle"]', "Status + tune + scores + save", "hard"),
        ("ai_arena", "Bataille arena", "ai_research", "lance l'arena", '["ai_arena_battle"]', "Matchs + ranking", "normal"),
        ("ai_rag", "Pipeline RAG", "ai_research", "pipeline rag", '["ai_rag_pipeline"]', "Index + embed + retrieve + rapport", "hard"),
        ("ai_hallucination", "Check hallucinations", "ai_research", "detecte les hallucinations", '["ai_hallucination_check"]', "QA factuel + test 3 modeles", "hard"),
        ("ai_quality", "Audit qualite", "ai_research", "audit qualite ia", '["ai_quality_audit"]', "Sample + score M2/GEMINI + rapport", "hard"),

        # Security
        ("sec_audit", "Audit complet", "security", "audit securite complet", '["sec_full_audit"]', "System + network + ports + rapport", "hard"),
        ("sec_ports", "Scan ports", "security", "scan les ports", '["sec_port_scan"]', "netstat + analyse + rapport", "easy"),
        ("sec_firewall", "Check firewall", "security", "verifie le firewall", '["sec_firewall_check"]', "Profiles + rules + rapport", "easy"),
        ("sec_process", "Audit processus", "security", "audit des processus", '["sec_process_audit"]', "Top procs + analyse + rapport", "normal"),
        ("sec_updates", "Check mises a jour", "security", "verifie les mises a jour", '["sec_update_check"]', "winget upgrade + rapport", "easy"),
        ("sec_vuln", "Scan vulnerabilites", "security", "scan de vulnerabilites", '["sec_vulnerability_scan"]', "Deps + code + rapport", "hard"),

        # Data Engineering
        ("data_backup", "Backup complet", "data_eng", "backup les bases", '["data_backup_full"]', "Backup etoile + jarvis + trading", "easy"),
        ("data_optimize", "Optimise BDD", "data_eng", "optimise les bases", '["data_db_optimize"]', "Vacuum + analyze + stats", "normal"),
        ("data_export", "Export JSON", "data_eng", "exporte en json", '["data_export_json"]', "Export pipelines/scenarios/commands", "easy"),
        ("data_integrity", "Check integrite", "data_eng", "verifie l'integrite", '["data_integrity_check"]', "FK + doublons + orphelins", "normal"),
        ("data_stats", "Dashboard stats", "data_eng", "dashboard de stats", '["data_stats_dashboard"]', "Count + usage + trends", "normal"),
        ("data_validation", "Validation scenarios", "data_eng", "validation des scenarios", '["data_scenario_validation"]', "Run cycle + rapport + fix", "hard"),

        # Monitoring
        ("mon_health", "Sante systeme", "monitoring", "sante systeme", '["mon_system_health"]', "CPU + RAM + GPU + disque", "easy"),
        ("mon_thermal", "Boucle thermique", "monitoring", "boucle thermique gpu", '["mon_gpu_thermal_loop"]', "3 checks + trend", "easy"),
        ("mon_latency", "Latence reseau", "monitoring", "latence du cluster", '["mon_network_latency"]', "Ping 3 machines", "easy"),
        ("mon_ollama", "Sante ollama", "monitoring", "sante ollama", '["mon_ollama_health"]', "Tags + models + rapport", "easy"),
        ("mon_lmstudio", "Sante LM Studio", "monitoring", "sante lm studio", '["mon_lmstudio_health"]', "Models 3 machines", "easy"),
        ("mon_services", "Check services", "monitoring", "verification services", '["mon_service_check"]', "6 ports + rapport", "easy"),

        # Routines
        ("routine_morning", "Routine matin", "routine", "routine du matin", '["routine_morning_full"]', "Check + GPU + trading + calendar + meteo", "normal"),
        ("routine_evening", "Routine soir", "routine", "routine du soir", '["routine_evening_full"]', "PnL + cluster + save + backup", "normal"),
        ("routine_work", "Debut travail", "routine", "debut de session", '["routine_work_start"]', "Check + VS Code + terminal + Github", "easy"),
        ("routine_end_work", "Fin travail", "routine", "fin de session", '["routine_work_end"]', "Git + save + summary + standby", "easy"),
        ("routine_trading_s", "Session trading", "routine", "session trading", '["routine_trading_session"]', "Conditions + portfolio + scan + risk", "normal"),
        ("routine_maint", "Maintenance", "routine", "maintenance hebdomadaire", '["routine_maintenance"]', "Backup + clean + vacuum + bench", "hard"),
        ("routine_debug", "Debug session", "routine", "session de debug", '["routine_debug_session"]', "Check + error context + tools", "normal"),
        ("routine_review", "Review session", "routine", "session de revue", '["routine_review_session"]', "Git log + quality + review", "normal"),
        ("routine_learning", "Mode apprentissage", "routine", "mode apprentissage", '["routine_learning_mode"]', "Autolearn + improve + rapport", "hard"),
        ("routine_night", "Mode nuit", "routine", "mode nuit", '["routine_night_mode"]', "Save + backup + hibernate", "easy"),

        # Emergency
        ("emg_node", "Noeud en panne", "emergency", "noeud en panne", '["emg_node_down"]', "Identify + reroute + heal + verify", "hard"),
        ("emg_overheat", "Surchauffe GPU", "emergency", "surchauffe gpu", '["emg_gpu_overheat"]', "Check + reduce + fan + verify", "hard"),
        ("emg_disk", "Disque plein", "emergency", "disque plein", '["emg_disk_full"]', "Usage + clean temp + clean cache", "normal"),
        ("emg_network", "Reseau down", "emergency", "reseau en panne", '["emg_network_down"]', "Ping + release + renew", "hard"),
        ("emg_ollama", "Ollama crash", "emergency", "ollama crash", '["emg_ollama_crash"]', "Kill + restart + verify", "normal"),
        ("emg_restart", "Restart cluster", "emergency", "redemarre le cluster", '["emg_full_cluster_restart"]', "Save + shutdown + start + verify", "hard"),
        ("emg_trading", "Arret trading", "emergency", "arret d'urgence trading", '["emg_trading_halt"]', "Cancel + close + disable", "hard"),

        # Consensus
        ("cons_code", "Revue code 3 agents", "consensus", "revue code multi-agent", '["cons_code_review_3way"]', "M1 + M2 + M3 review + merge", "normal"),
        ("cons_archi", "Vote architecture", "consensus", "vote architecture", '["cons_architecture_vote"]', "GEMINI propose + M1/M2 review", "hard"),
        ("cons_bug", "Chasse aux bugs", "consensus", "chasse aux bugs", '["cons_bug_hunt"]', "3 agents analyse + consensus + fix", "hard"),
        ("cons_trading", "Signal trading 4way", "consensus", "signal trading multi", '["cons_trading_signal_4way"]', "4 agents analyse + consensus", "hard"),
        ("cons_decision", "Decision 6 agents", "consensus", "decision complete", '["cons_decision_6way"]', "6 agents analyse + vote pondere", "hard"),
        ("cons_quality", "Porte qualite", "consensus", "porte qualite", '["cons_quality_gate"]', "3 agents check + decision", "normal"),

        # Integration
        ("int_n8n_scan", "N8N scan", "integration", "declenche n8n scan", '["int_n8n_trigger_scan"]', "Trigger + status + result", "normal"),
        ("int_telegram", "Alerte telegram", "integration", "alerte telegram", '["int_telegram_alert"]', "Format + send + confirm", "easy"),
        ("int_github", "Sync github", "integration", "synchronise github", '["int_github_sync"]', "Pull + check + push", "easy"),
        ("int_hf_export", "Export HuggingFace", "integration", "exporte vers hugging face", '["int_export_hf"]', "Prepare + validate + upload", "normal"),
        ("int_publish", "Multi-platform publish", "integration", "publie partout", '["int_multi_platform_publish"]', "Github + HF + Telegram", "hard"),

        # Optimization
        ("opt_model", "Swap modele perf", "optimization", "swap modele performance", '["opt_model_swap_perf"]', "Bench + swap + bench + compare", "hard"),
        ("opt_routing", "Rebalance routage", "optimization", "reequilibre le routage", '["opt_routing_rebalance"]', "Stats + detect + adjust", "normal"),
        ("opt_latency", "Minimise latence", "optimization", "minimise la latence", '["opt_latency_minimize"]', "Profile + bottleneck + optimize", "normal"),
        ("opt_weights", "Auto-tune poids", "optimization", "auto-tune les poids", '["opt_weight_autotune"]', "Collect + calc + apply", "hard"),

        # Multimodal
        ("mm_tts", "Text to speech", "multimodal", "text to speech", '["mm_tts_pipeline"]', "Prepare + generate + play", "easy"),
        ("mm_stt", "Speech to text", "multimodal", "speech to text", '["mm_stt_pipeline"]', "Record + transcribe + process", "normal"),
        ("mm_translate", "Traduction", "multimodal", "traduis ca", '["mm_translate_pipeline"]', "Detect + translate + verify", "normal"),
        ("mm_explain", "Explique code", "multimodal", "explique le code", '["mm_code_explain"]', "Read + explain M1/M2 + merge", "normal"),
        ("mm_report", "Genere rapport", "multimodal", "genere un rapport", '["mm_report_gen"]', "Collect + analyze + format + PDF", "hard"),
    ]

    for name, desc, cat, voice, expected, result, diff in scenario_templates:
        scenarios.append((name, desc, cat, voice, expected, result, diff))

    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
# 5. INSERTION
# ══════════════════════════════════════════════════════════════════════════════

def insert_all():
    """Insert everything into the databases."""
    print("=" * 80)
    print(f"  PIPELINE FACTORY v1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)

    # ── ETOILE.DB ──
    conn_e = sqlite3.connect(ETOILE_DB)
    cur_e = conn_e.cursor()

    # Count existing
    cur_e.execute("SELECT COUNT(*) FROM pipeline_dictionary")
    existing_pipes = cur_e.fetchone()[0]
    cur_e.execute("SELECT COUNT(*) FROM domino_chains")
    existing_chains = cur_e.fetchone()[0]
    cur_e.execute("SELECT COUNT(*) FROM scenario_weights")
    existing_weights = cur_e.fetchone()[0]

    print(f"\n  Existants: {existing_pipes} pipelines | {existing_chains} dominos | {existing_weights} weights")

    # Insert pipelines
    pipelines = gen_pipelines()
    p_inserted = 0
    p_skipped = 0
    for pid, trigger, steps, category, atype, agents in pipelines:
        try:
            cur_e.execute(
                "INSERT INTO pipeline_dictionary (pipeline_id, trigger_phrase, steps, category, action_type, agents_involved) VALUES (?,?,?,?,?,?)",
                (pid, trigger, steps, category, atype, agents)
            )
            p_inserted += 1
        except sqlite3.IntegrityError:
            p_skipped += 1
    conn_e.commit()
    print(f"\n  PIPELINES: {p_inserted} inseres, {p_skipped} deja existants")

    # Insert domino chains
    chains = gen_domino_chains()
    c_inserted = 0
    c_skipped = 0
    for trigger, condition, next_cmd, delay, auto, desc in chains:
        try:
            cur_e.execute(
                "INSERT INTO domino_chains (trigger_cmd, condition, next_cmd, delay_ms, auto, description) VALUES (?,?,?,?,?,?)",
                (trigger, condition, next_cmd, delay, auto, desc)
            )
            c_inserted += 1
        except sqlite3.IntegrityError:
            c_skipped += 1
    conn_e.commit()
    print(f"  DOMINO CHAINS: {c_inserted} inserees, {c_skipped} deja existantes")

    # Insert scenario weights
    weights = gen_scenario_weights()
    w_inserted = 0
    w_skipped = 0
    for scenario, agent, weight, priority, chain_next, desc in weights:
        try:
            cur_e.execute(
                "INSERT INTO scenario_weights (scenario, agent, weight, priority, chain_next, description) VALUES (?,?,?,?,?,?)",
                (scenario, agent, weight, priority, chain_next, desc)
            )
            w_inserted += 1
        except sqlite3.IntegrityError:
            w_skipped += 1
    conn_e.commit()
    print(f"  SCENARIO WEIGHTS: {w_inserted} inseres, {w_skipped} deja existants")

    # Final counts etoile.db
    cur_e.execute("SELECT COUNT(*) FROM pipeline_dictionary")
    total_pipes = cur_e.fetchone()[0]
    cur_e.execute("SELECT COUNT(*) FROM domino_chains")
    total_chains = cur_e.fetchone()[0]
    cur_e.execute("SELECT COUNT(*) FROM scenario_weights")
    total_weights = cur_e.fetchone()[0]
    conn_e.close()

    # ── JARVIS.DB ──
    conn_j = sqlite3.connect(JARVIS_DB)
    cur_j = conn_j.cursor()
    cur_j.execute("SELECT COUNT(*) FROM scenarios")
    existing_scenarios = cur_j.fetchone()[0]

    scenarios = gen_scenarios()
    s_inserted = 0
    s_skipped = 0
    for name, desc, cat, voice, expected, result, diff in scenarios:
        try:
            cur_j.execute(
                "INSERT INTO scenarios (name, description, category, voice_input, expected_commands, expected_result, difficulty) VALUES (?,?,?,?,?,?,?)",
                (name, desc, cat, voice, expected, result, diff)
            )
            s_inserted += 1
        except sqlite3.IntegrityError:
            s_skipped += 1
    conn_j.commit()

    cur_j.execute("SELECT COUNT(*) FROM scenarios")
    total_scenarios = cur_j.fetchone()[0]
    conn_j.close()

    # ── RAPPORT FINAL ──
    print(f"\n{'=' * 80}")
    print(f"  RAPPORT FINAL")
    print(f"{'=' * 80}")
    print(f"\n  ETOILE.DB:")
    print(f"    Pipelines:       {existing_pipes:>5} -> {total_pipes:>5} (+{p_inserted})")
    print(f"    Domino Chains:   {existing_chains:>5} -> {total_chains:>5} (+{c_inserted})")
    print(f"    Scenario Weights:{existing_weights:>5} -> {total_weights:>5} (+{w_inserted})")
    print(f"\n  JARVIS.DB:")
    print(f"    Scenarios:       {existing_scenarios:>5} -> {total_scenarios:>5} (+{s_inserted})")
    print(f"\n  TOTAL NOUVEAU: +{p_inserted + c_inserted + w_inserted + s_inserted} entrees")

    # Category breakdown
    conn_e = sqlite3.connect(ETOILE_DB)
    cur_e = conn_e.cursor()
    print(f"\n  PIPELINES PAR CATEGORIE:")
    cur_e.execute("SELECT category, COUNT(*) FROM pipeline_dictionary GROUP BY category ORDER BY COUNT(*) DESC")
    for cat, count in cur_e.fetchall():
        print(f"    {cat:20s} : {count:>4}")

    print(f"\n  DOMINO CHAINS CYCLIQUES:")
    cur_e.execute("SELECT COUNT(*) FROM domino_chains WHERE description LIKE '%CYCLE%'")
    cycles = cur_e.fetchone()[0]
    cur_e.execute("SELECT COUNT(*) FROM domino_chains")
    total = cur_e.fetchone()[0]
    print(f"    {cycles} chaines cycliques sur {total} total")
    conn_e.close()

    print(f"\n  Agents utilises: {', '.join(NODES)}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    insert_all()
