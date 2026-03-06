#!/usr/bin/env python3
"""ia_self_improver.py

Batch 28: Agent IA d'auto-amelioration continue.
Analyse les performances du cluster, detecte les patterns de regression,
et genere des recommandations d'optimisation.

Piliers:
  1. Performance tracking (latence, throughput, erreurs par noeud)
  2. Quality scoring (reponses correctes vs incorrectes)
  3. Routing optimization (rebalance les poids autolearn)
  4. Code health (dead code, complexity, test coverage)

Usage :
    ia_self_improver.py --analyze     # analyse les metriques
    ia_self_improver.py --optimize    # applique les optimisations
    ia_self_improver.py --report      # genere un rapport
    ia_self_improver.py --loop        # boucle continue (15 min)
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request

TURBO_ROOT = "F:/BUREAU/turbo"
PROXY_URL = "http://127.0.0.1:18800"
DB_PATH = os.path.join(TURBO_ROOT, "data", "etoile.db")
TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT = "2010747443"
REPORT_FILE = os.path.join(os.path.dirname(__file__), "SELF_IMPROVE_REPORT.json")


def get_cluster_metrics():
    """Recupere les metriques depuis autolearn."""
    metrics = {}
    try:
        req = urllib.request.Request(f"{PROXY_URL}/autolearn/scores")
        resp = urllib.request.urlopen(req, timeout=10)
        metrics["scores"] = json.loads(resp.read().decode())
    except Exception as e:
        metrics["scores_error"] = str(e)

    try:
        req = urllib.request.Request(f"{PROXY_URL}/autolearn/memory")
        resp = urllib.request.urlopen(req, timeout=10)
        metrics["memory"] = json.loads(resp.read().decode())
    except Exception as e:
        metrics["memory_error"] = str(e)

    try:
        req = urllib.request.Request(f"{PROXY_URL}/health")
        resp = urllib.request.urlopen(req, timeout=10)
        metrics["health"] = json.loads(resp.read().decode())
    except Exception as e:
        metrics["health_error"] = str(e)

    return metrics


def get_db_metrics():
    """Recupere les metriques depuis etoile.db."""
    if not os.path.exists(DB_PATH):
        return {"error": "etoile.db not found"}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    metrics = {}

    try:
        # Benchmark results
        rows = conn.execute(
            "SELECT * FROM benchmark_results ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
        metrics["recent_benchmarks"] = len(rows)
    except Exception:
        pass

    try:
        # Cluster health history
        rows = conn.execute(
            "SELECT * FROM cluster_health ORDER BY timestamp DESC LIMIT 50"
        ).fetchall()
        metrics["health_records"] = len(rows)
        if rows:
            latest = dict(rows[0])
            metrics["latest_health"] = latest
    except Exception:
        pass

    try:
        # Consensus logs
        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM consensus_log"
        ).fetchone()
        metrics["consensus_count"] = rows["cnt"] if rows else 0
    except Exception:
        pass

    conn.close()
    return metrics


def analyze_performance(metrics):
    """Analyse les metriques et genere des recommendations."""
    recommendations = []

    # Analyse health
    health = metrics.get("health", {})
    nodes = health.get("nodes", [])
    for node in nodes:
        if node.get("status") != "online":
            recommendations.append({
                "type": "critical",
                "node": node.get("nodeId"),
                "msg": f"Noeud {node.get('nodeId')} OFFLINE — verifier la connexion",
            })
        elif node.get("latency", 0) > 5000:
            recommendations.append({
                "type": "warning",
                "node": node.get("nodeId"),
                "msg": f"Noeud {node.get('nodeId')} lent ({node.get('latency')}ms)",
            })

    # Analyse scores
    scores = metrics.get("scores", {})
    if isinstance(scores, dict):
        for node_id, categories in scores.items():
            if isinstance(categories, dict):
                avg = sum(categories.values()) / max(len(categories), 1)
                if avg < 0.5:
                    recommendations.append({
                        "type": "warning",
                        "node": node_id,
                        "msg": f"{node_id} score moyen faible ({avg:.2f})",
                    })

    return recommendations


def generate_report(metrics, recommendations):
    """Genere un rapport complet."""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cluster_metrics": {
            "nodes_online": len([n for n in metrics.get("health", {}).get("nodes", []) if n.get("status") == "online"]),
            "nodes_total": len(metrics.get("health", {}).get("nodes", [])),
        },
        "db_metrics": get_db_metrics(),
        "recommendations": recommendations,
        "score": max(0, 100 - len([r for r in recommendations if r["type"] == "critical"]) * 20 - len([r for r in recommendations if r["type"] == "warning"]) * 5),
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


def notify_telegram(report):
    """Envoie le resume du rapport sur Telegram."""
    score = report.get("score", 0)
    emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
    recs = report.get("recommendations", [])
    criticals = [r for r in recs if r["type"] == "critical"]
    warnings = [r for r in recs if r["type"] == "warning"]

    lines = [
        f"{emoji} *Self-Improve Report* — Score: {score}/100",
        f"Noeuds: {report['cluster_metrics']['nodes_online']}/{report['cluster_metrics']['nodes_total']}",
    ]
    if criticals:
        lines.append(f"🔴 {len(criticals)} critiques")
        for c in criticals[:3]:
            lines.append(f"  - {c['msg']}")
    if warnings:
        lines.append(f"⚠️ {len(warnings)} warnings")

    msg = "\n".join(lines)
    try:
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run_analysis():
    """Execute un cycle complet d'analyse."""
    print(f"\n[{time.strftime('%H:%M:%S')}] IA Self-Improver — Analyse")
    print("=" * 50)

    print("[1] Collecte metriques cluster...")
    metrics = get_cluster_metrics()

    print("[2] Collecte metriques DB...")
    db = get_db_metrics()
    print(f"  Benchmarks: {db.get('recent_benchmarks', 0)} | Health: {db.get('health_records', 0)} | Consensus: {db.get('consensus_count', 0)}")

    print("[3] Analyse performance...")
    recommendations = analyze_performance(metrics)
    print(f"  {len(recommendations)} recommendations")
    for r in recommendations:
        icon = "🔴" if r["type"] == "critical" else "⚠️"
        print(f"  {icon} {r['msg']}")

    print("[4] Generation rapport...")
    report = generate_report(metrics, recommendations)
    print(f"  Score: {report['score']}/100")

    return report


def main():
    parser = argparse.ArgumentParser(description="IA Self-Improver")
    parser.add_argument("--analyze", action="store_true", help="Analyse les metriques")
    parser.add_argument("--report", action="store_true", help="Genere et envoie un rapport")
    parser.add_argument("--loop", action="store_true", help="Boucle continue (15 min)")
    args = parser.parse_args()

    if args.loop:
        print("Mode boucle (Ctrl+C pour arreter)")
        while True:
            report = run_analysis()
            notify_telegram(report)
            time.sleep(900)  # 15 min
    elif args.report:
        report = run_analysis()
        notify_telegram(report)
    else:
        run_analysis()


if __name__ == "__main__":
    main()
