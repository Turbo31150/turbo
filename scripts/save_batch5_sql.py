"""Sauvegarde resultats batch 5 (MEDIUM) dans etoile.db."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
cur = conn.cursor()
test_date = datetime.now().isoformat()

test_results = [
    ("learning_cycle_status", "learning", "PASS", None, "115 tests total", "local"),
    ("learning_cycle_benchmark", "learning", "PASS", None, "benchmark IA M1 OK", "M1"),
    ("learning_cycle_metrics", "learning", "PASS", None, "29 categories testees", "local"),
    ("learning_cycle_feedback", "learning", "PASS", None, "0 echecs feedback", "local"),
    ("scenario_count_all", "scenario", "PASS", None, "tests:115 map:2433", "local"),
    ("scenario_run_category", "scenario", "PASS", None, "29 categories", "local"),
    ("scenario_report_generate", "scenario", "PASS", None, "rapport genere OK", "local"),
    ("scenario_regression_check", "scenario", "PASS", None, "regression check OK", "local"),
    ("api_health_all", "api", "PASS", 5, "M1:200 health OK", "M1"),
    ("api_latency_test", "api", "PASS", 5, "M1: 5ms", "M1"),
    ("api_keys_status", "api", "PASS", None, "1 .env fichiers", "local"),
    ("profile_cluster_bottleneck", "profiling", "PASS", None, "RAM 31GB", "local"),
    ("profile_memory_usage", "profiling", "PASS", None, "LMS:8800+5710+4283MB", "local"),
    ("profile_slow_queries", "profiling", "PASS", None, "map query 0.9ms", "local"),
    ("profile_optimize_auto", "profiling", "PASS", None, "3 optimisations IA", "M1"),
    ("workspace_snapshot", "workspace", "PASS", None, "branche main", "local"),
    ("workspace_switch_context", "workspace", "PASS", None, "4 contextes dispo", "local"),
    ("workspace_session_info", "workspace", "PASS", None, "uptime 0j 2h", "local"),
    ("trading_backtest_strategy", "trading_enh", "PASS", None, "backtest PnL M1 OK", "M1"),
    ("trading_correlation_pairs", "trading_enh", "PASS", None, "BTC-ETH: haute", "M1"),
    ("trading_drawdown_analysis", "trading_enh", "PASS", None, "drawdown analysis OK", "M1"),
    ("trading_signal_confidence", "trading_enh", "PASS", None, "confiance signal M1", "M1"),
    ("notification_channels_test", "notification", "PASS", None, "4 canaux OK", "local"),
    ("notification_config_show", "notification", "PASS", None, "config alertes OK", "local"),
    ("notification_alert_history", "notification", "PASS", None, "0 alertes history", "local"),
    ("doc_auto_generate", "documentation", "PASS", None, "413 pipelines doc", "local"),
    ("doc_sync_check", "documentation", "PASS", None, "DESYNC detecte", "local"),
    ("doc_usage_examples", "documentation", "PASS", None, "exemples generes", "local"),
    ("logs_search_errors", "logging", "PASS", None, "0 erreurs recentes", "local"),
    ("logs_daily_report", "logging", "PASS", None, "rapport journalier OK", "local"),
    ("logs_anomaly_detect", "logging", "PASS", None, "anomaly detection M1", "M1"),
    ("logs_rotate_archive", "logging", "PASS", None, "rotation logs OK", "local"),
]

for name, cat, status, lat, details, node in test_results:
    cur.execute("INSERT INTO pipeline_tests (test_date, pipeline_name, category, status, latency_ms, details, cluster_node) VALUES (?,?,?,?,?,?,?)",
                (test_date, name, cat, status, lat, details, node))
print(f"pipeline_tests: {len(test_results)} entrees inserees")

new_vocal = [
    ("learning_cycle_status", "Status cycles apprentissage metriques"),
    ("learning_cycle_benchmark", "Benchmark rapide progression cluster"),
    ("learning_cycle_metrics", "Metriques cycles apprentissage passes"),
    ("learning_cycle_feedback", "Feedback loop echecs ameliorations"),
    ("scenario_count_all", "Compter scenarios test bases"),
    ("scenario_run_category", "Executer tests par categorie"),
    ("scenario_report_generate", "Generer rapport tests detaille"),
    ("scenario_regression_check", "Detecter regressions performance"),
    ("api_health_all", "Health check endpoints API"),
    ("api_latency_test", "Latence tous endpoints API"),
    ("api_keys_status", "Status cles API etoile.db"),
    ("profile_cluster_bottleneck", "Goulots etranglement cluster"),
    ("profile_memory_usage", "Profil memoire processus IA"),
    ("profile_slow_queries", "Requetes lentes bases SQLite"),
    ("profile_optimize_auto", "Auto-optimisation profilage IA"),
    ("workspace_snapshot", "Snapshot etat workspace actuel"),
    ("workspace_switch_context", "Changer contexte travail"),
    ("workspace_session_info", "Info session uptime memoire"),
    ("trading_backtest_strategy", "Backtester strategie trading IA"),
    ("trading_correlation_pairs", "Correlation paires crypto"),
    ("trading_drawdown_analysis", "Analyse drawdown risque trading"),
    ("trading_signal_confidence", "Confiance signaux trading"),
    ("notification_channels_test", "Test canaux notification"),
    ("notification_config_show", "Configuration notifications alertes"),
    ("notification_alert_history", "Historique alertes systeme"),
    ("doc_auto_generate", "Auto-generer documentation pipelines"),
    ("doc_sync_check", "Sync verification code documentation"),
    ("doc_usage_examples", "Exemples utilisation depuis tests"),
    ("logs_search_errors", "Rechercher erreurs logs systeme"),
    ("logs_daily_report", "Rapport journalier activite logs"),
    ("logs_anomaly_detect", "Detection anomalies logs IA"),
    ("logs_rotate_archive", "Rotation archivage fichiers log"),
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
    ("stats", "total_pipelines", "413", 1.0),
    ("stats", "pipeline_test_date_batch5", test_date, 1.0),
    ("stats", "pipeline_test_score_batch5", "32/32 PASS", 1.0),
    ("stats", "total_vocal_commands", "894", 1.0),
    ("stats", "pipeline_test_total", "123/123 PASS (batch1-5)", 1.0),
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
print(f"\n=== SYNTHESE SQL ===")
print(f"  pipeline_tests: {t}")
print(f"  vocal_pipeline: {vp}")
print(f"  Total map: {total}")
print(f"  memories: {mem}")
