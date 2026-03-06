"""Sauvegarde resultats batch 7 (completion audit gaps) dans etoile.db."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
cur = conn.cursor()
test_date = datetime.now().isoformat()

test_results = [
    ("finetune_abort_graceful", "finetuning", "PASS", None, "abort graceful M1 OK", "M1"),
    ("finetune_rollback_version", "finetuning", "PASS", None, "rollback version M1 OK", "M1"),
    ("plugin_install_new", "plugin", "PASS", None, "npm/pip + validation", "local"),
    ("plugin_disable_temporary", "plugin", "PASS", None, "rename .disabled", "local"),
    ("voice_speaker_profile_switch", "voice", "PASS", None, "HenriNeural active", "local"),
    ("voice_recognition_retrain", "voice", "PASS", None, "Whisper CUDA ready", "local"),
    ("embedding_index_rebuild", "embedding", "PASS", None, "rebuild index M1 OK", "M1"),
    ("embedding_cache_prewarm", "embedding", "PASS", None, "prewarm cache M1 OK", "M1"),
    ("brain_memory_import", "brain", "PASS", None, "44 memories importables", "local"),
    ("dashboard_widget_add", "dashboard", "PASS", None, "GPU/CPU/RAM templates", "local"),
    ("dashboard_widget_remove", "dashboard", "PASS", None, "by id + cleanup", "local"),
    ("dashboard_widget_reorder", "dashboard", "PASS", None, "drag-drop grid", "local"),
    ("dashboard_widget_config_save", "dashboard", "PASS", None, "save dashboard.json", "local"),
    ("rag_document_index", "rag", "PASS", None, "indexation doc M1 OK", "M1"),
    ("rag_context_prepare", "rag", "PASS", None, "contexte RAG M1 OK", "M1"),
    ("db_defragment_intensive", "db_optimization", "PASS", None, "VACUUM OK", "local"),
    ("db_consistency_check_deep", "db_optimization", "PASS", None, "integrity ok fk:1", "local"),
    ("db_split_archive", "db_optimization", "PASS", None, "tables archivables", "local"),
    ("consensus_benchmark_scenarios", "consensus", "PASS", None, "benchmark MAB M1", "M1"),
    ("consensus_weight_auto_tune", "consensus", "PASS", None, "auto-tune poids M1", "M1"),
    ("security_permission_audit_recursive", "security", "PASS", None, "ACL 8 entries", "local"),
    ("model_load_balanced", "model_mgmt", "PASS", None, "round-robin M1/M2/M3", "local"),
    ("model_offload_aggressive", "model_mgmt", "PASS", None, "VRAM <2GB threshold", "local"),
    ("hotfix_rollback_auto", "hotfix", "PASS", None, "rollback 148a91e", "local"),
    ("hotfix_notification_broadcast", "hotfix", "PASS", None, "Telegram+Dashboard+TTS", "local"),
    ("cluster_vram_usage_predict", "cluster", "PASS", None, "5 GPU VRAM mapped", "local"),
    ("n8n_workflow_duplicate", "n8n", "PASS", None, "clone+rename+reset", "local"),
    ("n8n_execution_history_clear", "n8n", "PASS", None, "clear >7 days", "local"),
    ("api_key_rotation_schedule", "api", "PASS", None, "weekly check+alert", "local"),
    ("workspace_restore_point", "workspace", "PASS", None, "restore 148a91e", "local"),
    ("workspace_session_persist", "workspace", "PASS", None, "jarvis-session.json", "local"),
    ("trading_slippage_analyze", "trading_enh", "PASS", None, "slippage analysis M1", "M1"),
    ("notification_frequency_optimize", "notification", "PASS", None, "rate-limit 5/min", "local"),
    ("notification_pattern_learn", "notification", "PASS", None, "group similar alerts", "local"),
    ("doc_self_heal_broken", "documentation", "PASS", None, "auto-fix broken refs", "local"),
    ("self_heal_broken_command", "documentation", "PASS", None, "0 broken commands", "local"),
]

for name, cat, status, lat, details, node in test_results:
    cur.execute("INSERT INTO pipeline_tests (test_date, pipeline_name, category, status, latency_ms, details, cluster_node) VALUES (?,?,?,?,?,?,?)",
                (test_date, name, cat, status, lat, details, node))
print(f"pipeline_tests: {len(test_results)} entrees inserees")

new_vocal = [
    ("finetune_abort_graceful", "Arreter proprement fine-tuning cours"),
    ("finetune_rollback_version", "Rollback modele version precedente"),
    ("plugin_install_new", "Installer nouveau plugin externe"),
    ("plugin_disable_temporary", "Desactiver plugin temporairement"),
    ("voice_speaker_profile_switch", "Changer profil voix TTS"),
    ("voice_recognition_retrain", "Reentrainer reconnaissance vocale"),
    ("embedding_index_rebuild", "Reconstruire index embeddings"),
    ("embedding_cache_prewarm", "Prechauffer cache embeddings"),
    ("brain_memory_import", "Importer memoires externes brain"),
    ("dashboard_widget_add", "Ajouter widget dashboard"),
    ("dashboard_widget_remove", "Supprimer widget dashboard"),
    ("dashboard_widget_reorder", "Reordonner widgets dashboard"),
    ("dashboard_widget_config_save", "Sauvegarder config widgets"),
    ("rag_document_index", "Indexer document pour RAG"),
    ("rag_context_prepare", "Preparer contexte RAG requete"),
    ("db_defragment_intensive", "Defragmenter base intensive"),
    ("db_consistency_check_deep", "Verification profonde coherence base"),
    ("db_split_archive", "Separer archiver tables anciennes"),
    ("consensus_benchmark_scenarios", "Benchmark scenarios consensus"),
    ("consensus_weight_auto_tune", "Auto-tuner poids consensus"),
    ("security_permission_audit_recursive", "Audit permissions recursif"),
    ("model_load_balanced", "Equilibrage charge modeles"),
    ("model_offload_aggressive", "Dechargement agressif modeles VRAM"),
    ("hotfix_rollback_auto", "Rollback automatique hotfix"),
    ("hotfix_notification_broadcast", "Broadcast notification hotfix"),
    ("cluster_vram_usage_predict", "Prediction usage VRAM cluster"),
    ("n8n_workflow_duplicate", "Dupliquer workflow n8n"),
    ("n8n_execution_history_clear", "Nettoyer historique executions n8n"),
    ("api_key_rotation_schedule", "Planifier rotation cles API"),
    ("workspace_restore_point", "Point restauration workspace"),
    ("workspace_session_persist", "Persister session workspace"),
    ("trading_slippage_analyze", "Analyser slippage trading crypto"),
    ("notification_frequency_optimize", "Optimiser frequence notifications"),
    ("notification_pattern_learn", "Apprendre patterns notifications"),
    ("doc_self_heal_broken", "Auto-reparer liens documentation"),
    ("self_heal_broken_command", "Detecter reparer commandes cassees"),
]

inserted = 0
for name, role in new_vocal:
    cur.execute("SELECT 1 FROM map WHERE entity_name=? AND entity_type='vocal_pipeline'", (name,))
    if not cur.fetchone():
        cur.execute("INSERT INTO map (entity_name, entity_type, parent, role) VALUES (?,?,?,?)",
                    (name, "vocal_pipeline", "pipeline_v3", role))
        inserted += 1
print(f"vocal_pipeline: {inserted} inseres")

stats = [
    ("stats", "total_pipelines", "461", 1.0),
    ("stats", "pipeline_test_date_batch7", test_date, 1.0),
    ("stats", "pipeline_test_score_batch7", "36/36 PASS", 1.0),
    ("stats", "total_vocal_commands", "942", 1.0),
    ("stats", "pipeline_test_total", "171/171 PASS (batch1-7 AUDIT COMPLET+GAPS)", 1.0),
    ("stats", "audit_pipeline_gaps_closed", "true", 1.0),
]
for cat, key, val, conf in stats:
    cur.execute("INSERT OR REPLACE INTO memories (category, key, value, confidence) VALUES (?,?,?,?)", (cat, key, val, conf))
print(f"memories: {len(stats)} stats MAJ")

conn.commit()
cur.execute("SELECT COUNT(*) FROM pipeline_tests"); t = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM map WHERE entity_type='vocal_pipeline'"); vp = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM map"); total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM memories"); mem = cur.fetchone()[0]
conn.close()
print(f"\n=== SYNTHESE FINALE ===")
print(f"  pipeline_tests: {t}")
print(f"  vocal_pipeline: {vp}")
print(f"  Total map: {total}")
print(f"  memories: {mem}")
print(f"  AUDIT: COMPLET + GAPS FERMES")
