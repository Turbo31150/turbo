#!/usr/bin/env python3
"""intent_classifier.py

Classificateur d'intentions pour commandes JARVIS.
Analyse un texte utilisateur et détermine l'intention (catégorie + action).

CLI :
    --classify TEXT   : Classifier une intention
    --batch FILE      : Classifier un fichier (1 ligne = 1 requête)
    --stats           : Statistiques des classifications (SQLite)
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

DB_PATH = Path(__file__).parent / "intents.db"

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

# Intent categories et keywords
INTENT_MAP = {
    "system": {
        "keywords": ["status", "cpu", "ram", "gpu", "température", "thermal", "mémoire", "disque", "espace", "performance", "benchmark", "processus", "services"],
        "actions": ["check_status", "benchmark", "optimize", "monitor"]
    },
    "trading": {
        "keywords": ["trading", "trade", "bitcoin", "btc", "eth", "sol", "crypto", "mexc", "futures", "signal", "prix", "price", "short", "long", "portfolio"],
        "actions": ["scan", "analyze", "backtest", "report"]
    },
    "email": {
        "keywords": ["email", "mail", "inbox", "message", "envoie", "envoyer", "lire", "lis", "courrier", "gmail"],
        "actions": ["read", "send", "search"]
    },
    "network": {
        "keywords": ["réseau", "network", "ping", "wifi", "bluetooth", "usb", "connexion", "internet", "latence"],
        "actions": ["scan", "monitor", "connect"]
    },
    "file": {
        "keywords": ["fichier", "file", "dossier", "folder", "organise", "backup", "sauvegarde", "copie", "screenshot", "capture"],
        "actions": ["organize", "backup", "search", "export"]
    },
    "ai": {
        "keywords": ["ia", "ai", "modèle", "model", "cluster", "ollama", "lmstudio", "gemini", "claude", "agent", "consensus"],
        "actions": ["query", "consensus", "route", "health"]
    },
    "voice": {
        "keywords": ["voix", "voice", "parle", "dis", "tts", "audio", "volume", "son", "microphone"],
        "actions": ["speak", "adjust", "train"]
    },
    "automation": {
        "keywords": ["automatise", "cron", "planifie", "schedule", "tâche", "task", "workflow", "pipeline", "rapport", "report"],
        "actions": ["create", "schedule", "run", "report"]
    },
    "security": {
        "keywords": ["sécurité", "security", "scan", "virus", "firewall", "registre", "registry", "driver", "pilote", "restore"],
        "actions": ["scan", "audit", "backup", "restore"]
    },
    "general": {
        "keywords": ["bonjour", "salut", "aide", "help", "merci", "ok", "oui", "non", "quoi", "comment"],
        "actions": ["greet", "help", "confirm"]
    }
}

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS classifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        input_text TEXT NOT NULL,
        category TEXT NOT NULL,
        action TEXT,
        confidence REAL,
        model_used TEXT
    )""")
    conn.commit()
    return conn

def classify_local(text: str) -> Tuple[str, str, float]:
    """Classification par keywords (rapide, pas d'IA)."""
    text_lower = text.lower()
    scores = {}
    for cat, data in INTENT_MAP.items():
        score = sum(1 for kw in data["keywords"] if kw in text_lower)
        if score > 0:
            scores[cat] = score

    if not scores:
        return "general", "help", 0.3

    best_cat = max(scores, key=scores.get)
    confidence = min(1.0, scores[best_cat] / 3)

    # Determine action
    action = INTENT_MAP[best_cat]["actions"][0]
    action_keywords = {
        "lire": "read", "lis": "read", "read": "read",
        "envoie": "send", "send": "send",
        "scan": "scan", "scanner": "scan",
        "rapport": "report", "report": "report",
        "crée": "create", "create": "create",
        "status": "check_status", "état": "check_status",
    }
    for kw, act in action_keywords.items():
        if kw in text_lower:
            if act in INTENT_MAP[best_cat]["actions"] or True:
                action = act
                break

    return best_cat, action, confidence

def classify_ai(text: str) -> Optional[Tuple[str, str, float]]:
    """Classification via OL1 (Ollama) pour plus de précision."""
    categories = ", ".join(INTENT_MAP.keys())
    prompt = f"Classifie cette requête utilisateur dans une catégorie. Catégories: {categories}. Réponds UNIQUEMENT avec le JSON: {{\"category\": \"...\", \"action\": \"...\", \"confidence\": 0.9}}. Requête: {text}"
    try:
        result = subprocess.check_output([
            "curl", "-s", "--max-time", "10",
            "http://127.0.0.1:11434/api/chat",
            "-d", json.dumps({
                "model": "qwen3:1.7b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False
            })
        ], text=True, timeout=15)
        data = json.loads(result)
        content = data.get("message", {}).get("content", "")
        # Extract JSON from response
        match = re.search(r'\{[^}]+\}', content)
        if match:
            parsed = json.loads(match.group())
            return parsed.get("category", "general"), parsed.get("action", "help"), parsed.get("confidence", 0.7)
    except Exception:
        pass
    return None

def classify(text: str, use_ai: bool = False) -> Dict:
    cat, action, conf = classify_local(text)
    model = "keywords"

    if use_ai or conf < 0.5:
        ai_result = classify_ai(text)
        if ai_result:
            cat, action, conf = ai_result
            model = "qwen3:1.7b"
            conf = max(conf, 0.6)

    return {
        "input": text,
        "category": cat,
        "action": action,
        "confidence": round(conf, 2),
        "model": model,
        "timestamp": datetime.now().isoformat()
    }

def show_stats():
    if not DB_PATH.is_file():
        print("[intent_classifier] Aucune donnée.")
        return
    conn = sqlite3.connect(str(DB_PATH))
    total = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
    cats = conn.execute("SELECT category, COUNT(*), AVG(confidence) FROM classifications GROUP BY category ORDER BY COUNT(*) DESC").fetchall()
    conn.close()

    print(f"=== Statistiques Intent Classifier ===")
    print(f"Total classifications : {total}")
    if cats:
        print(f"\nPar catégorie :")
        for cat, cnt, avg_conf in cats:
            print(f"  {cat:15} : {cnt:4} ({avg_conf:.2f} confiance moyenne)")

def main():
    parser = argparse.ArgumentParser(description="Classificateur d'intentions JARVIS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--classify", metavar="TEXT", help="Classifier une intention")
    group.add_argument("--batch", metavar="FILE", help="Classifier un fichier")
    group.add_argument("--stats", action="store_true", help="Statistiques")
    parser.add_argument("--ai", action="store_true", help="Utiliser OL1 pour classification avancée")
    args = parser.parse_args()

    if args.classify:
        result = classify(args.classify, use_ai=args.ai)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # Log
        conn = init_db()
        conn.execute("INSERT INTO classifications (timestamp, input_text, category, action, confidence, model_used) VALUES (?,?,?,?,?,?)",
                     (result["timestamp"], result["input"], result["category"], result["action"], result["confidence"], result["model"]))
        conn.commit()
        conn.close()

    elif args.batch:
        p = Path(args.batch)
        if not p.is_file():
            print(f"[intent_classifier] Fichier introuvable : {args.batch}")
            return
        conn = init_db()
        lines = p.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            result = classify(line, use_ai=args.ai)
            print(f"  [{result['category']:12}] {result['action']:15} ({result['confidence']:.2f}) — {line[:50]}")
            conn.execute("INSERT INTO classifications (timestamp, input_text, category, action, confidence, model_used) VALUES (?,?,?,?,?,?)",
                         (result["timestamp"], result["input"], result["category"], result["action"], result["confidence"], result["model"]))
        conn.commit()
        conn.close()

    elif args.stats:
        show_stats()

if __name__ == "__main__":
    main()
