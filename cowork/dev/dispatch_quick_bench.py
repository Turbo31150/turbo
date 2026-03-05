#!/usr/bin/env python3
"""Quick dispatch benchmark — 14 pattern types x 1 prompt = 14 dispatches.

Runs one representative prompt per pattern to measure current success rate.
Results stored in etoile.db (benchmark_runs table) for trend analysis.
Designed to run as a cron every 30min to track improvements.

Usage:
    python dev/dispatch_quick_bench.py --once
    python dev/dispatch_quick_bench.py --help
"""

import argparse
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# One representative prompt per pattern
BENCH_PROMPTS = {
    "classifier": "Classifie cette tache: deployer un microservice avec CI/CD",
    "simple": "Bonjour, quelle est la capitale de la France?",
    "web": "Recherche les derniers prix du Bitcoin",
    "code": "Ecris une fonction Python qui parse du JSON imbriqué avec gestion d'erreurs",
    "analysis": "Compare PostgreSQL vs MySQL: performance, scalabilité, cas d'usage",
    "system": "Liste les processus Windows qui consomment le plus de RAM",
    "creative": "Ecris un haiku sur l'intelligence artificielle",
    "math": "Calcule la derivee de f(x) = x^3 * ln(x)",
    "data": "Ecris une requete SQL pour trouver les doublons dans une table users",
    "devops": "Comment configurer un pipeline CI/CD GitHub Actions pour Python?",
    "reasoning": "Si tous les chats sont des animaux et certains animaux sont rapides, peut-on conclure que certains chats sont rapides?",
    "trading": "Analyse technique BTC: RSI, MACD, Bollinger. Signal?",
    "security": "Identifie les vulnerabilites OWASP dans: query = f'SELECT * FROM users WHERE id={user_id}'",
    "architecture": "Design un systeme de notification en temps reel pour 1M utilisateurs",
}

DB_PATH = "F:/BUREAU/turbo/etoile.db"


async def run_benchmark():
    try:
        from src.pattern_agents import PatternAgentRegistry
        import httpx
    except ImportError:
        print(json.dumps({"error": "Cannot import pattern_agents"}, ensure_ascii=False))
        return

    registry = PatternAgentRegistry()
    results = []
    t0 = time.time()

    async with httpx.AsyncClient() as client:
        for pattern, prompt in BENCH_PROMPTS.items():
            agent = registry.agents.get(pattern)
            if not agent:
                results.append({"pattern": pattern, "ok": False, "error": "no agent"})
                continue
            try:
                r = await agent.execute(client, prompt)
                results.append({
                    "pattern": pattern,
                    "ok": r.ok,
                    "node": r.node,
                    "strategy": r.strategy,
                    "ms": round(r.latency_ms),
                    "tokens": r.tokens,
                    "quality": round(r.quality_score, 3),
                    "content_len": len(r.content),
                })
            except Exception as e:
                results.append({"pattern": pattern, "ok": False, "error": str(e)[:100]})

    duration = round(time.time() - t0, 1)
    ok_count = sum(1 for r in results if r.get("ok"))
    total = len(results)
    rate = ok_count / max(1, total)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "ok": ok_count,
        "rate": f"{rate*100:.1f}%",
        "duration_s": duration,
        "results": results,
        "failed_patterns": [r["pattern"] for r in results if not r.get("ok")],
    }

    # Store in DB
    try:
        db = sqlite3.connect(DB_PATH)
        db.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_quick (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ok INTEGER, total INTEGER, rate REAL,
                duration_s REAL, details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute(
            "INSERT INTO benchmark_quick (ok, total, rate, duration_s, details) VALUES (?,?,?,?,?)",
            (ok_count, total, rate, duration, json.dumps(results, ensure_ascii=False)),
        )
        db.commit()
        db.close()
    except Exception:
        pass

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description="Quick dispatch benchmark (14 patterns)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    asyncio.run(run_benchmark())


if __name__ == "__main__":
    main()
