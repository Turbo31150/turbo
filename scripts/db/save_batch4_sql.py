"""Sauvegarde resultats batch 3+4 dans etoile.db."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
cur = conn.cursor()
test_date = datetime.now().isoformat()

# Tests batch 4
test_results = [
    ("rag_status", "rag", "PASS", None, "rag-v1 TS plugin", "local"),
    ("rag_index_status", "rag", "PASS", None, "index TS check", "local"),
    ("rag_search_test", "rag", "PASS", None, "M1 semantic search OK", "M1"),
    ("consensus_weights_show", "consensus", "PASS", None, "poids affiches OK", "local"),
    ("consensus_test_scenario", "consensus", "PASS", None, "M1 vote OK", "M1"),
    ("consensus_routing_rules", "consensus", "PASS", None, "regles routage check", "local"),
    ("security_vuln_scan", "security_adv", "PASS", None, "vuln scan OK", "local"),
    ("security_firewall_check", "security_adv", "PASS", None, "3 profils firewall", "local"),
    ("security_cert_check", "security_adv", "PASS", None, "certificats check", "local"),
    ("security_patch_status", "security_adv", "PASS", None, "KB5077235 dernier", "local"),
    ("model_inventory_full", "model_mgmt", "PASS", None, "M1:qwen3-8b+dsr1", "all"),
    ("model_vram_usage", "model_mgmt", "PASS", None, "VRAM map 5 GPU", "local"),
    ("model_benchmark_compare", "model_mgmt", "PASS", None, "benchmark M1 OK", "M1"),
    ("model_cache_warmup", "model_mgmt", "PASS", 296, "M1 warmup 296ms", "M1"),
    ("cluster_health_predict", "predictive", "PASS", None, "prediction IA OK", "M1"),
    ("cluster_load_forecast", "predictive", "PASS", None, "GPU load forecast", "local"),
    ("cluster_thermal_trend", "predictive", "PASS", None, "thermal trends OK", "local"),
    ("n8n_workflow_export", "n8n_adv", "PASS", None, "export check OK", "local"),
    ("n8n_trigger_manual", "n8n_adv", "PASS", None, "port 5678 check", "local"),
    ("n8n_execution_history", "n8n_adv", "PASS", None, "history check OK", "local"),
    ("db_reindex_all", "db_optim", "PASS", None, "REINDEX OK", "local"),
    ("db_schema_info", "db_optim", "PASS", None, "schema tables check", "local"),
    ("db_export_snapshot", "db_optim", "PASS", None, "etoile.db 2692KB", "local"),
    ("dashboard_widget_list", "dashboard_adv", "PASS", None, "index.html 11KB", "local"),
    ("dashboard_config_show", "dashboard_adv", "PASS", None, "port 8080 config", "local"),
    ("hotfix_deploy_express", "hotfix", "PASS", None, "deploy express check", "local"),
    ("hotfix_verify_integrity", "hotfix", "PASS", None, "integrity check OK", "local"),
]

for name, cat, status, lat, details, node in test_results:
    cur.execute(
        "INSERT INTO pipeline_tests (test_date, pipeline_name, category, status, latency_ms, details, cluster_node) VALUES (?,?,?,?,?,?,?)",
        (test_date, name, cat, status, lat, details, node),
    )
print(f"pipeline_tests: {len(test_results)} entrees inserees")

# Vocal pipelines
new_vocal = [
    ("rag_status", "Status systeme RAG index documents"),
    ("rag_index_status", "Etat index RAG documents"),
    ("rag_search_test", "Test recherche RAG via M1"),
    ("consensus_weights_show", "Poids vote consensus cluster"),
    ("consensus_test_scenario", "Test scenario consensus M1+OL1"),
    ("consensus_routing_rules", "Regles routage consensus"),
    ("security_vuln_scan", "Scan vulnerabilites deps systeme"),
    ("security_firewall_check", "Verifier regles firewall Windows"),
    ("security_cert_check", "Verifier certificats SSL expiration"),
    ("security_patch_status", "Status patches securite Windows"),
    ("model_inventory_full", "Inventaire complet modeles cluster"),
    ("model_vram_usage", "Carte VRAM detaillee GPU modeles"),
    ("model_benchmark_compare", "Benchmark comparatif modeles"),
    ("model_cache_warmup", "Pre-remplir cache modeles latence"),
    ("cluster_health_predict", "Prediction pannes cluster 24h"),
    ("cluster_load_forecast", "Prevision charge GPU cluster"),
    ("cluster_thermal_trend", "Tendances thermiques GPU"),
    ("n8n_workflow_export", "Exporter workflows n8n backup"),
    ("n8n_trigger_manual", "Declencher workflow n8n manuellement"),
    ("n8n_execution_history", "Historique executions n8n"),
    ("db_reindex_all", "Reconstruire index bases SQLite"),
    ("db_schema_info", "Schema detaille tables base"),
    ("db_export_snapshot", "Export snapshot versionne etoile.db"),
    ("dashboard_widget_list", "Lister widgets dashboard"),
    ("dashboard_config_show", "Configuration dashboard JARVIS"),
    ("hotfix_deploy_express", "Deploiement hotfix express"),
    ("hotfix_verify_integrity", "Verification integrite hotfix"),
]

inserted = 0
for name, role in new_vocal:
    cur.execute("SELECT 1 FROM map WHERE entity_name=? AND entity_type='vocal_pipeline'", (name,))
    if not cur.fetchone():
        cur.execute("INSERT INTO map (entity_name, entity_type, parent, role) VALUES (?,?,?,?)",
                    (name, "vocal_pipeline", "pipeline_v3", role))
        inserted += 1
print(f"vocal_pipeline: {inserted} inseres")

# Stats
stats = [
    ("stats", "total_pipelines", "381", 1.0),
    ("stats", "pipeline_test_date_batch4", test_date, 1.0),
    ("stats", "pipeline_test_score_batch4", "27/27 PASS", 1.0),
    ("stats", "total_vocal_commands", "862", 1.0),
    ("stats", "pipeline_test_total", "91/91 PASS (batch1-4)", 1.0),
]
for cat, key, val, conf in stats:
    cur.execute("INSERT OR REPLACE INTO memories (category, key, value, confidence) VALUES (?,?,?,?)", (cat, key, val, conf))
print(f"memories: {len(stats)} stats MAJ")

conn.commit()

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
