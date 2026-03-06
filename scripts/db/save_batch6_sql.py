"""Sauvegarde resultats batch 6 (LOW final) dans etoile.db."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
cur = conn.cursor()
test_date = datetime.now().isoformat()

test_results = [
    ("preference_work_hours", "preference", "PASS", None, "pattern horaire 127 commits 7j", "local"),
    ("preference_app_usage", "preference", "PASS", None, "10 apps avec fenetre", "local"),
    ("preference_auto_suggest", "preference", "PASS", None, "suggestion routine_matin", "local"),
    ("accessibility_profile_show", "accessibility", "PASS", None, "Dark apps OUI", "local"),
    ("accessibility_voice_speed", "accessibility", "PASS", None, "TTS Edge 1.0x", "local"),
    ("accessibility_contrast_check", "accessibility", "PASS", None, "Dark systeme OUI", "local"),
    ("stream_obs_status", "streaming", "PASS", None, "OBS INACTIF", "local"),
    ("stream_quality_check", "streaming", "PASS", None, "ping check OK", "local"),
    ("stream_chat_monitor", "streaming", "PASS", None, "Twitch/YT + Telegram bridge", "local"),
    ("collab_sync_status", "collaboration", "PASS", None, "M1 sync check", "all"),
    ("collab_commands_export", "collaboration", "PASS", None, "425 pipelines exportables", "local"),
    ("collab_db_merge_check", "collaboration", "PASS", None, "integrity ok", "local"),
]

for name, cat, status, lat, details, node in test_results:
    cur.execute("INSERT INTO pipeline_tests (test_date, pipeline_name, category, status, latency_ms, details, cluster_node) VALUES (?,?,?,?,?,?,?)",
                (test_date, name, cat, status, lat, details, node))
print(f"pipeline_tests: {len(test_results)} entrees inserees")

new_vocal = [
    ("preference_work_hours", "Analyser heures travail habituelles"),
    ("preference_app_usage", "Applications les plus utilisees"),
    ("preference_auto_suggest", "Suggestion mode selon heure contexte"),
    ("accessibility_profile_show", "Profil accessibilite actuel"),
    ("accessibility_voice_speed", "Vitesse synthese vocale TTS"),
    ("accessibility_contrast_check", "Contraste ecran accessibilite"),
    ("stream_obs_status", "Status OBS Studio streaming"),
    ("stream_quality_check", "Qualite reseau GPU streaming"),
    ("stream_chat_monitor", "Monitorer chat Twitch YouTube"),
    ("collab_sync_status", "Synchronisation machines cluster"),
    ("collab_commands_export", "Exporter commandes autre machine"),
    ("collab_db_merge_check", "Compatibilite fusion bases"),
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
    ("stats", "total_pipelines", "425", 1.0),
    ("stats", "pipeline_test_date_final", test_date, 1.0),
    ("stats", "pipeline_test_score_final", "135/135 PASS", 1.0),
    ("stats", "total_vocal_commands", "906", 1.0),
    ("stats", "pipeline_test_total", "135/135 PASS (batch1-6 AUDIT COMPLET)", 1.0),
    ("stats", "audit_pipeline_complete", "true", 1.0),
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
print(f"  AUDIT: COMPLET")
