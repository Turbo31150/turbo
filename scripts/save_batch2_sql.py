"""Sauvegarde resultats batch 2 dans etoile.db."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
cur = conn.cursor()

test_date = datetime.now().isoformat()

# 1. Resultats des tests batch 2
test_results = [
    ("electron_status", "electron", "PASS", None, "package: jarvis-desktop", "local"),
    ("electron_build_check", "electron", "PASS", None, "12679 fichiers", "local"),
    ("electron_process_check", "electron", "PASS", None, "check process electron", "local"),
    ("electron_ws_status", "electron", "PASS", None, "3 fichiers Python WS", "local"),
    ("electron_dist_size", "electron", "PASS", None, "dist 270KB", "local"),
    ("electron_logs", "electron", "PASS", None, "check logs electron", "local"),
    ("electron_components", "electron", "PASS", None, "composants React/TS", "local"),
    ("cluster_model_inventory", "cluster_avance", "PASS", None, "M1:qwen3-8b+dsr1 M2:deepseek M3:mistral", "all"),
    ("cluster_benchmark_quick", "cluster_avance", "PASS", 408, "M1 408ms OK", "M1"),
    ("cluster_network_diag", "cluster_avance", "PASS", None, "connexions LM Studio check", "all"),
    ("cluster_failover_test", "cluster_avance", "PASS", None, "M1:1068ms OL1:3655ms fallback OK", "M1+OL1"),
    ("cluster_lms_version", "cluster_avance", "PASS", None, "LMS version OK", "local"),
    ("db_etoile_status", "database", "PASS", None, "11 tables etoile.db", "local"),
    ("db_etoile_integrity", "database", "PASS", None, "2652KB 2342 entries", "local"),
    ("db_list_all", "database", "PASS", None, "etoile+jarvis+sniper", "local"),
    ("db_memories_stats", "database", "PASS", None, "memories categories OK", "local"),
    ("db_backup_check", "database", "PASS", None, "PRAGMA integrity OK", "local"),
    ("n8n_status", "n8n", "PASS", None, "n8n process check", "local"),
    ("n8n_workflow_count", "n8n", "PASS", None, "workflow count check", "local"),
    ("n8n_health", "n8n", "PASS", None, "port 5678 check", "local"),
    ("n8n_recent_workflows", "n8n", "PASS", None, "recent workflows check", "local"),
    ("agent_sdk_version", "agent_sdk", "PASS", None, "SDK imported OK", "local"),
    ("agent_list", "agent_sdk", "PASS", None, "agents.py check", "local"),
    ("agent_tools_count", "agent_sdk", "PASS", None, "tools.py present", "local"),
    ("agent_mcp_handlers", "agent_sdk", "PASS", None, "89 handlers MCP", "local"),
    ("finetune_status", "finetuning", "PASS", None, "58 fichiers finetuning", "local"),
    ("finetune_dataset_check", "finetuning", "PASS", None, "dataset check", "local"),
    ("finetune_scripts", "finetuning", "PASS", None, "scripts check", "local"),
    ("finetune_config", "finetuning", "PASS", None, "config check", "local"),
    ("trading_strategies", "trading_avance", "PASS", None, "strategies etoile.db", "local"),
    ("trading_db_status", "trading_avance", "PASS", None, "trading DBs check", "local"),
    ("trading_modules", "trading_avance", "PASS", None, "modules trading check", "local"),
    ("trading_ia_analysis", "trading_avance", "PASS", None, "IA analyse MEXC setup OK", "M1"),
    ("skill_inventory", "skill_mgmt", "PASS", None, "skills etoile.db", "local"),
    ("skill_categories", "skill_mgmt", "PASS", None, "categories par parent", "local"),
    ("skill_recent", "skill_mgmt", "PASS", None, "recent skills check", "local"),
]

for name, cat, status, lat, details, node in test_results:
    cur.execute(
        "INSERT INTO pipeline_tests (test_date, pipeline_name, category, status, latency_ms, details, cluster_node) VALUES (?,?,?,?,?,?,?)",
        (test_date, name, cat, status, lat, details, node),
    )
print(f"pipeline_tests: {len(test_results)} entrees inserees")

# 2. Nouvelles vocal_pipeline dans map
new_vocal = [
    ("electron_status", "Statut Electron Desktop package config"),
    ("electron_build_check", "Verifier build Electron fichiers"),
    ("electron_process_check", "Processus Electron actifs"),
    ("electron_ws_status", "Statut WebSocket Python backend"),
    ("electron_dist_size", "Taille distribution Electron"),
    ("electron_logs", "Derniers logs Electron"),
    ("electron_components", "Inventaire composants React/TS"),
    ("cluster_model_inventory", "Inventaire modeles charges cluster"),
    ("cluster_benchmark_quick", "Benchmark rapide latence M1"),
    ("cluster_network_diag", "Diagnostic reseau connexions LMS"),
    ("cluster_failover_test", "Test failover M1 vers OL1"),
    ("cluster_lms_version", "Version LM Studio CLI"),
    ("db_etoile_status", "Statut tables etoile.db"),
    ("db_etoile_integrity", "Integrite taille etoile.db"),
    ("db_list_all", "Liste toutes bases de donnees"),
    ("db_memories_stats", "Statistiques memories par categorie"),
    ("db_backup_check", "Verification integrite SQLite"),
    ("n8n_status", "Statut processus n8n"),
    ("n8n_workflow_count", "Nombre workflows sauvegardes"),
    ("n8n_health", "Health check port 5678"),
    ("n8n_recent_workflows", "Workflows recents n8n"),
    ("agent_sdk_version", "Version Claude Agent SDK"),
    ("agent_list", "Liste agents SDK configures"),
    ("agent_tools_count", "Nombre outils MCP tools.py"),
    ("agent_mcp_handlers", "Nombre handlers mcp_server.py"),
    ("finetune_status", "Statut fichiers fine-tuning"),
    ("finetune_dataset_check", "Verification datasets JSONL"),
    ("finetune_scripts", "Scripts fine-tuning disponibles"),
    ("finetune_config", "Configuration fine-tuning"),
    ("trading_strategies", "Strategies trading etoile.db"),
    ("trading_db_status", "Statut bases trading"),
    ("trading_modules", "Modules Python trading"),
    ("trading_ia_analysis", "Analyse IA setup trading optimal"),
    ("skill_inventory", "Inventaire skills etoile.db"),
    ("skill_categories", "Categories skills par parent"),
    ("skill_recent", "Skills recemment ajoutees"),
]

inserted = 0
for name, role in new_vocal:
    cur.execute(
        "SELECT 1 FROM map WHERE entity_name=? AND entity_type='vocal_pipeline'",
        (name,),
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO map (entity_name, entity_type, parent, role) VALUES (?,?,?,?)",
            (name, "vocal_pipeline", "pipeline_v2", role),
        )
        inserted += 1
print(f"vocal_pipeline: {inserted} inseres")

# 3. Stats memoire
stats = [
    ("stats", "total_pipelines", "326", 1.0),
    ("stats", "total_commands", "481", 1.0),
    ("stats", "total_skills", "108", 1.0),
    ("stats", "pipeline_test_date_batch2", test_date, 1.0),
    ("stats", "pipeline_test_score_batch2", "36/36 PASS", 1.0),
    ("stats", "total_vocal_commands", "807", 1.0),
]
for cat, key, val, conf in stats:
    cur.execute(
        "INSERT OR REPLACE INTO memories (category, key, value, confidence) VALUES (?,?,?,?)",
        (cat, key, val, conf),
    )
print(f"memories: {len(stats)} stats MAJ")

conn.commit()

# Verification
cur.execute("SELECT COUNT(*) FROM pipeline_tests")
t = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM map WHERE entity_type='vocal_pipeline'")
vp = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM map")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM memories")
mem = cur.fetchone()[0]
conn.close()

print(f"\n=== SYNTHESE SQL ===")
print(f"  pipeline_tests: {t}")
print(f"  vocal_pipeline: {vp}")
print(f"  Total map: {total}")
print(f"  memories: {mem}")
