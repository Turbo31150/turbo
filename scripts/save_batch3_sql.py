"""Sauvegarde resultats batch 3 dans etoile.db."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
cur = conn.cursor()

test_date = datetime.now().isoformat()

# 1. Resultats des tests batch 3
test_results = [
    ("canvas_autolearn_status", "canvas", "PASS", None, "status port 18800", "local"),
    ("canvas_autolearn_trigger", "canvas", "PASS", None, "trigger cycle apprentissage", "local"),
    ("canvas_memory_review", "canvas", "PASS", None, "review memoire canvas", "local"),
    ("canvas_scoring_update", "canvas", "PASS", None, "update scores routing", "local"),
    ("canvas_autolearn_history", "canvas", "PASS", None, "historique cycles", "local"),
    ("voice_wake_word_test", "voice", "PASS", None, "test wake word jarvis", "local"),
    ("voice_latency_check", "voice", "PASS", None, "Whisper+Edge+LRU200", "local"),
    ("voice_cache_stats", "voice", "PASS", None, "38 refs cache voice.py", "local"),
    ("voice_fallback_chain", "voice", "PASS", None, "OL1:200 GEMINI:dispo Local:OK", "local+OL1"),
    ("voice_config_show", "voice", "PASS", None, "voice.py:21KB voice_correction:26KB", "local"),
    ("plugin_list_enabled", "plugin", "PASS", None, "plugins actifs check", "local"),
    ("plugin_jarvis_status", "plugin", "PASS", None, "jarvis-turbo plugin check", "local"),
    ("plugin_health_check", "plugin", "PASS", None, "local:1 cache:7", "local"),
    ("plugin_reload_config", "plugin", "PASS", None, "settings.json check", "local"),
    ("plugin_config_show", "plugin", "PASS", None, "jarvis-turbo config", "local"),
    ("embedding_model_status", "embedding", "PASS", None, "M1 qwen3-8b OK", "M1"),
    ("embedding_search_test", "embedding", "PASS", None, "semantic search M1 OK", "M1"),
    ("embedding_cache_status", "embedding", "PASS", None, "etoile.db 2680KB", "local"),
    ("embedding_generate_batch", "embedding", "PASS", None, "batch embed M1 OK", "M1"),
    ("finetune_monitor_progress", "finetune_orch", "PASS", None, "aucun training en cours", "local"),
    ("finetune_validate_quality", "finetune_orch", "PASS", None, "5 metriques qualite IA", "M1"),
    ("finetune_dataset_stats", "finetune_orch", "PASS", None, "58 fichiers finetuning", "local"),
    ("finetune_export_lora", "finetune_orch", "PASS", None, "0 checkpoints", "local"),
    ("brain_memory_status", "brain", "PASS", None, "34 memories 11 categories", "local"),
    ("brain_pattern_learn", "brain", "PASS", None, "pattern dev recurrent IA", "M1"),
    ("brain_memory_consolidate", "brain", "PASS", None, "0 doublons", "local"),
    ("brain_memory_export", "brain", "PASS", None, "34 entries exportables", "local"),
    ("brain_pattern_search", "brain", "PASS", None, "patterns recents OK", "local"),
]

for name, cat, status, lat, details, node in test_results:
    cur.execute(
        "INSERT INTO pipeline_tests (test_date, pipeline_name, category, status, latency_ms, details, cluster_node) VALUES (?,?,?,?,?,?,?)",
        (test_date, name, cat, status, lat, details, node),
    )
print(f"pipeline_tests: {len(test_results)} entrees inserees")

# 2. Nouvelles vocal_pipeline dans map
new_vocal = [
    ("canvas_autolearn_status", "Status complet moteur Canvas Autolearn"),
    ("canvas_autolearn_trigger", "Declencher cycle apprentissage Canvas"),
    ("canvas_memory_review", "Revoir memoire Canvas Autolearn"),
    ("canvas_scoring_update", "Mettre a jour scores routing Canvas"),
    ("canvas_autolearn_history", "Historique cycles apprentissage Canvas"),
    ("voice_wake_word_test", "Test sensibilite wake word jarvis"),
    ("voice_latency_check", "Mesurer latence pipeline vocale"),
    ("voice_cache_stats", "Statistiques cache vocal LRU"),
    ("voice_fallback_chain", "Test chaine fallback vocale"),
    ("voice_config_show", "Configuration systeme vocal"),
    ("plugin_list_enabled", "Lister plugins Claude Code actifs"),
    ("plugin_jarvis_status", "Status plugin jarvis-turbo"),
    ("plugin_health_check", "Health check tous plugins"),
    ("plugin_reload_config", "Recharger config plugins"),
    ("plugin_config_show", "Configuration complete plugins"),
    ("embedding_model_status", "Status modele embedding M1"),
    ("embedding_search_test", "Test recherche semantique M1"),
    ("embedding_cache_status", "Status cache embeddings"),
    ("embedding_generate_batch", "Generer embeddings batch M1"),
    ("finetune_monitor_progress", "Monitoring fine-tuning temps reel"),
    ("finetune_validate_quality", "Validation qualite post-training"),
    ("finetune_dataset_stats", "Stats dataset fine-tuning"),
    ("finetune_export_lora", "Export poids LoRA"),
    ("brain_memory_status", "Status memoire JARVIS patterns"),
    ("brain_pattern_learn", "Apprendre pattern interactions"),
    ("brain_memory_consolidate", "Consolider memoire doublons"),
    ("brain_memory_export", "Exporter memoire JSON"),
    ("brain_pattern_search", "Rechercher patterns appris"),
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
            (name, "vocal_pipeline", "pipeline_v3", role),
        )
        inserted += 1
print(f"vocal_pipeline: {inserted} inseres")

# 3. Stats memoire
stats = [
    ("stats", "total_pipelines", "354", 1.0),
    ("stats", "pipeline_test_date_batch3", test_date, 1.0),
    ("stats", "pipeline_test_score_batch3", "28/28 PASS", 1.0),
    ("stats", "total_vocal_commands", "835", 1.0),
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
