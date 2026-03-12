#!/usr/bin/env python3
"""jarvis_intent_classifier.py — Classifieur d'intention avance.

Categorise les requetes utilisateur par domaine/action (TF-IDF simple).

Usage:
    python dev/jarvis_intent_classifier.py --once
    python dev/jarvis_intent_classifier.py --train
    python dev/jarvis_intent_classifier.py --classify "TEXT"
    python dev/jarvis_intent_classifier.py --accuracy
"""
import argparse
import json
import math
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "intent_classifier.db"

CATEGORIES = {
    "code": ["code", "script", "python", "function", "debug", "fix", "bug", "class", "compile", "test"],
    "trading": ["trading", "mexc", "bitcoin", "btc", "eth", "prix", "crypto", "futures", "position"],
    "system": ["gpu", "cpu", "ram", "disk", "temperature", "process", "service", "driver", "update"],
    "voice": ["commande", "vocale", "dis", "parle", "repete", "ecoute", "micro", "tts"],
    "web": ["cherche", "google", "site", "page", "navigateur", "url", "lien", "internet"],
    "cluster": ["cluster", "m1", "m2", "ollama", "modele", "agent", "noeud", "benchmark"],
    "file": ["fichier", "dossier", "copie", "deplace", "supprime", "renomme", "ouvre"],
    "automation": ["automatise", "cron", "schedule", "pipeline", "workflow", "tache"],
    "monitoring": ["monitore", "surveille", "alerte", "health", "status", "check"],
    "communication": ["telegram", "mail", "message", "envoie", "notifie"],
    "database": ["base", "donnees", "sqlite", "table", "requete", "sql"],
    "config": ["config", "parametre", "regle", "setting", "preference"],
    "help": ["aide", "help", "comment", "explique", "montre"],
    "entertainment": ["musique", "video", "joue", "youtube", "spotify"],
    "other": [],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS classifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, text TEXT, predicted TEXT,
        confidence REAL, scores TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS training (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_docs INTEGER, accuracy REAL,
        categories_count INTEGER)""")
    db.commit()
    return db


def tokenize(text):
    """Simple tokenizer."""
    import re
    return re.findall(r'[a-zA-Zéèêëàâùûîïôç]{2,}', text.lower())


def classify_text(text):
    """Classify text into a category using keyword matching (TF-IDF-like)."""
    tokens = tokenize(text)
    if not tokens:
        return "other", 0.0, {}

    scores = {}
    for cat, keywords in CATEGORIES.items():
        if not keywords:
            continue
        # Count keyword matches
        matches = sum(1 for t in tokens if t in keywords)
        # Weighted by inverse category frequency (more specific = higher weight)
        idf = math.log(len(CATEGORIES) / max(1, len(keywords)))
        scores[cat] = round(matches * idf / max(len(tokens), 1), 4)

    if not scores or max(scores.values()) == 0:
        return "other", 0.1, scores

    best_cat = max(scores, key=scores.get)
    confidence = min(scores[best_cat] * 2, 1.0)  # Scale up

    return best_cat, round(confidence, 3), scores


def do_train():
    """Train/evaluate the classifier."""
    db = init_db()

    # Test data
    test_data = [
        ("ecris un script python qui trie une liste", "code"),
        ("quel est le prix du bitcoin", "trading"),
        ("quelle est la temperature du gpu", "system"),
        ("dis bonjour", "voice"),
        ("cherche sur google les dernieres news", "web"),
        ("verifie le statut du cluster m1", "cluster"),
        ("copie ce fichier dans le dossier backup", "file"),
        ("lance le pipeline de monitoring", "automation"),
        ("envoie un message telegram", "communication"),
        ("optimise la base de donnees sqlite", "database"),
    ]

    correct = 0
    results = []
    for text, expected in test_data:
        predicted, confidence, scores = classify_text(text)
        is_correct = predicted == expected
        if is_correct:
            correct += 1
        results.append({
            "text": text[:60], "expected": expected,
            "predicted": predicted, "correct": is_correct,
            "confidence": confidence,
        })

    accuracy = correct / max(len(test_data), 1)

    db.execute(
        "INSERT INTO training (ts, total_docs, accuracy, categories_count) VALUES (?,?,?,?)",
        (time.time(), len(test_data), accuracy, len(CATEGORIES))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "accuracy": round(accuracy, 3),
        "correct": correct,
        "total": len(test_data),
        "categories": len(CATEGORIES),
        "results": results,
    }


def do_classify(text):
    """Classify a single text."""
    db = init_db()
    predicted, confidence, scores = classify_text(text)

    db.execute(
        "INSERT INTO classifications (ts, text, predicted, confidence, scores) VALUES (?,?,?,?,?)",
        (time.time(), text[:200], predicted, confidence, json.dumps(scores))
    )
    db.commit()
    db.close()

    top_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "text": text[:100],
        "category": predicted,
        "confidence": confidence,
        "top_categories": [{"cat": c, "score": s} for c, s in top_scores],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Intent Classifier")
    parser.add_argument("--once", "--train", action="store_true", help="Train and evaluate")
    parser.add_argument("--classify", metavar="TEXT", help="Classify text")
    parser.add_argument("--accuracy", action="store_true", help="Show accuracy")
    parser.add_argument("--confusion", action="store_true", help="Confusion matrix")
    args = parser.parse_args()

    if args.classify:
        result = do_classify(args.classify)
    else:
        result = do_train()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
