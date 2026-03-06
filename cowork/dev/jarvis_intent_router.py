#!/usr/bin/env python3
"""jarvis_intent_router.py (#198) — Intent classifier + router.

Keywords to category (code/trading/system/voice/web/general).
Maps to best agent per MAO routing matrix weights.

Usage:
    python dev/jarvis_intent_router.py --once
    python dev/jarvis_intent_router.py --route "Fix the bug in trading bot"
    python dev/jarvis_intent_router.py --rules
    python dev/jarvis_intent_router.py --stats
"""
import argparse
import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "intent_router.db"

# Intent categories with keyword patterns
INTENT_RULES = {
    "code": {
        "keywords": [
            "code", "function", "class", "bug", "fix", "refactor", "test", "debug",
            "implement", "python", "javascript", "typescript", "rust", "api",
            "endpoint", "module", "import", "error", "exception", "compile",
            "lint", "format", "review", "commit", "merge", "pr", "pull request",
            "script", "write", "create file", "edit", "modify", "patch",
            "coder", "programmer", "coding", "dev", "develop", "build"
        ],
        "weight": 1.5,
        "description": "Code generation, debugging, review"
    },
    "trading": {
        "keywords": [
            "trading", "trade", "buy", "sell", "signal", "btc", "eth", "sol",
            "crypto", "futures", "leverage", "position", "portfolio", "pnl",
            "profit", "loss", "mexc", "exchange", "market", "price", "candle",
            "indicator", "rsi", "macd", "volume", "backtest", "strategy",
            "usdt", "long", "short", "tp", "sl", "stop loss", "take profit"
        ],
        "weight": 1.4,
        "description": "Trading operations and analysis"
    },
    "system": {
        "keywords": [
            "system", "windows", "process", "service", "gpu", "cpu", "ram",
            "memory", "disk", "network", "firewall", "registry", "driver",
            "update", "install", "restart", "shutdown", "boot", "startup",
            "temperature", "thermal", "monitor", "watchdog", "health",
            "cluster", "node", "ollama", "lm studio", "model", "load",
            "power", "battery", "optimize", "performance", "benchmark"
        ],
        "weight": 1.2,
        "description": "System administration and monitoring"
    },
    "voice": {
        "keywords": [
            "voice", "vocal", "speak", "say", "tts", "whisper", "audio",
            "microphone", "wake word", "jarvis", "commande vocale",
            "dictation", "transcribe", "speech", "pronunciation",
            "filler", "domino", "trigger", "intent"
        ],
        "weight": 1.1,
        "description": "Voice commands and TTS"
    },
    "web": {
        "keywords": [
            "web", "search", "google", "url", "http", "browser", "website",
            "page", "scrape", "crawl", "fetch", "download", "api call",
            "rest", "graphql", "webhook", "internet", "online", "news"
        ],
        "weight": 1.0,
        "description": "Web search and browsing"
    },
    "general": {
        "keywords": [
            "help", "explain", "what", "how", "why", "define", "compare",
            "list", "show", "tell", "describe", "summarize", "translate"
        ],
        "weight": 0.8,
        "description": "General questions and tasks"
    }
}

# MAO routing: category -> ordered agent list with weights
MAO_ROUTING = {
    "code": [
        {"agent": "M1/qwen3-8b", "weight": 1.8, "role": "primary"},
        {"agent": "M2/deepseek-r1", "weight": 1.5, "role": "secondary"},
        {"agent": "OL1/qwen3:1.7b", "weight": 1.3, "role": "verifier"},
    ],
    "trading": [
        {"agent": "OL1/minimax", "weight": 1.3, "role": "primary"},
        {"agent": "M1/qwen3-8b", "weight": 1.8, "role": "secondary"},
    ],
    "system": [
        {"agent": "M1/qwen3-8b", "weight": 1.8, "role": "primary"},
        {"agent": "OL1/qwen3:1.7b", "weight": 1.3, "role": "secondary"},
    ],
    "voice": [
        {"agent": "OL1/qwen3:1.7b", "weight": 1.3, "role": "primary"},
        {"agent": "M1/qwen3-8b", "weight": 1.8, "role": "secondary"},
    ],
    "web": [
        {"agent": "OL1/minimax", "weight": 1.3, "role": "primary"},
        {"agent": "GEMINI", "weight": 1.2, "role": "secondary"},
    ],
    "general": [
        {"agent": "OL1/qwen3:1.7b", "weight": 1.3, "role": "primary"},
        {"agent": "M1/qwen3-8b", "weight": 1.8, "role": "fallback"},
    ]
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS routing_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        input_text TEXT,
        detected_intent TEXT,
        confidence REAL,
        matched_keywords TEXT,
        routed_to TEXT,
        all_scores TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS routing_stats (
        intent TEXT PRIMARY KEY,
        route_count INTEGER DEFAULT 0,
        avg_confidence REAL DEFAULT 0,
        last_routed REAL
    )""")
    db.commit()
    return db


def classify_intent(text):
    """Classify text into an intent category."""
    text_lower = text.lower()
    words = set(re.findall(r'\w+', text_lower))

    scores = {}
    matched = {}

    for intent, config in INTENT_RULES.items():
        score = 0
        matches = []
        for kw in config["keywords"]:
            if " " in kw:
                # Multi-word keyword
                if kw in text_lower:
                    score += 2 * config["weight"]
                    matches.append(kw)
            else:
                if kw in words:
                    score += 1 * config["weight"]
                    matches.append(kw)

        scores[intent] = round(score, 2)
        matched[intent] = matches

    # Find winner
    if not any(scores.values()):
        return "general", 0.5, [], scores

    best_intent = max(scores, key=scores.get)
    total_score = sum(scores.values())
    confidence = round(scores[best_intent] / max(total_score, 1), 2) if total_score > 0 else 0.5

    return best_intent, confidence, matched.get(best_intent, []), scores


def route_text(db, text):
    """Classify intent and route to best agent."""
    intent, confidence, matched_kw, all_scores = classify_intent(text)
    agents = MAO_ROUTING.get(intent, MAO_ROUTING["general"])

    primary = agents[0] if agents else {"agent": "OL1", "weight": 1.0, "role": "primary"}

    # Log
    db.execute(
        """INSERT INTO routing_log
           (ts, input_text, detected_intent, confidence, matched_keywords, routed_to, all_scores)
           VALUES (?,?,?,?,?,?,?)""",
        (time.time(), text[:500], intent, confidence,
         json.dumps(matched_kw), primary["agent"], json.dumps(all_scores))
    )

    # Update stats
    db.execute("""INSERT INTO routing_stats (intent, route_count, avg_confidence, last_routed)
                  VALUES (?, 1, ?, ?)
                  ON CONFLICT(intent) DO UPDATE SET
                  route_count=route_count+1,
                  avg_confidence=((avg_confidence * route_count) + ?) / (route_count + 1),
                  last_routed=?""",
               (intent, confidence, time.time(), confidence, time.time()))
    db.commit()

    return {
        "status": "ok",
        "input": text[:200],
        "intent": intent,
        "confidence": confidence,
        "matched_keywords": matched_kw,
        "route": {
            "primary": primary,
            "agents": agents
        },
        "all_scores": all_scores
    }


def list_rules():
    """Show all intent rules."""
    rules = {}
    for intent, config in INTENT_RULES.items():
        rules[intent] = {
            "keyword_count": len(config["keywords"]),
            "weight": config["weight"],
            "description": config["description"],
            "sample_keywords": config["keywords"][:10],
            "agents": [a["agent"] for a in MAO_ROUTING.get(intent, [])]
        }
    return {"status": "ok", "intents": rules}


def get_stats(db):
    """Get routing statistics."""
    total = db.execute("SELECT COUNT(*) FROM routing_log").fetchone()[0]

    rows = db.execute(
        "SELECT intent, route_count, avg_confidence, last_routed FROM routing_stats ORDER BY route_count DESC"
    ).fetchall()
    stats = []
    for r in rows:
        stats.append({
            "intent": r[0],
            "count": r[1],
            "avg_confidence": round(r[2], 2),
            "last_routed": datetime.fromtimestamp(r[3]).isoformat() if r[3] else "never"
        })

    # Recent routes
    recent = db.execute(
        "SELECT ts, input_text, detected_intent, confidence, routed_to FROM routing_log ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    recent_list = []
    for r in recent:
        recent_list.append({
            "time": datetime.fromtimestamp(r[0]).isoformat(),
            "input": r[1][:80], "intent": r[2],
            "confidence": r[3], "agent": r[4]
        })

    return {
        "status": "ok",
        "total_routes": total,
        "by_intent": stats,
        "recent": recent_list
    }


def once(db):
    """Run once: demo routing + stats."""
    demos = [
        "Fix the bug in trading bot signal handler",
        "What is the current GPU temperature?",
        "Search the web for Python 3.13 release notes",
        "Explain how async/await works"
    ]
    results = []
    for demo in demos:
        r = route_text(db, demo)
        results.append({
            "input": demo,
            "intent": r["intent"],
            "confidence": r["confidence"],
            "agent": r["route"]["primary"]["agent"]
        })

    stats = get_stats(db)

    return {
        "status": "ok", "mode": "once",
        "demo_routes": results,
        "stats": stats
    }


def main():
    parser = argparse.ArgumentParser(description="Intent Router (#198) — Classify and route to agents")
    parser.add_argument("--route", type=str, help="Route a text to the best agent")
    parser.add_argument("--rules", action="store_true", help="Show intent rules")
    parser.add_argument("--stats", action="store_true", help="Show routing statistics")
    parser.add_argument("--once", action="store_true", help="Run once with demo")
    args = parser.parse_args()

    db = init_db()

    if args.route:
        result = route_text(db, args.route)
    elif args.rules:
        result = list_rules()
    elif args.stats:
        result = get_stats(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
