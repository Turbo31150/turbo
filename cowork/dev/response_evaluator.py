#!/usr/bin/env python3
"""response_evaluator.py — Evalue la qualite des reponses IA du cluster.

Compare les reponses de differents noeuds, score la qualite,
detecte les hallucinations, mesure la coherence.

Usage:
    python dev/response_evaluator.py --eval "prompt" "reponse"
    python dev/response_evaluator.py --compare "prompt"          # Compare tous les noeuds
    python dev/response_evaluator.py --score "texte"             # Score un texte
    python dev/response_evaluator.py --history                   # Historique
    python dev/response_evaluator.py --leaderboard              # Classement noeuds
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "evaluator.db"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, prompt_preview TEXT, node TEXT,
        response_length INTEGER, score_relevance REAL,
        score_completeness REAL, score_format REAL,
        score_total REAL, details TEXT)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Scoring heuristics (sans IA externe)
# ---------------------------------------------------------------------------
def score_response(prompt: str, response: str) -> dict:
    """Score une reponse selon plusieurs criteres."""
    scores = {}

    # 1. Relevance: response relates to prompt keywords
    prompt_words = set(re.findall(r'\w{3,}', prompt.lower()))
    response_words = set(re.findall(r'\w{3,}', response.lower()))
    overlap = len(prompt_words & response_words)
    scores["relevance"] = min(overlap / max(len(prompt_words), 1) * 100, 100)

    # 2. Completeness: response length relative to prompt complexity
    prompt_complexity = len(prompt.split())
    response_length = len(response.split())
    if prompt_complexity < 10:  # simple question
        expected_min = 5
    elif prompt_complexity < 30:  # medium
        expected_min = 20
    else:  # complex
        expected_min = 50
    scores["completeness"] = min(response_length / expected_min * 100, 100) if expected_min > 0 else 0

    # 3. Format quality
    format_score = 50  # base
    if response.strip():
        format_score += 10
    if len(response) > 10:
        format_score += 10
    if not response.startswith("ERROR"):
        format_score += 10
    # Bonus for structured responses
    if any(c in response for c in ['{', '[', '```', '|', '\n- ', '\n1.']):
        format_score += 10
    # Penalty for very short
    if len(response) < 20:
        format_score -= 20
    # Penalty for repeating prompt
    if prompt.lower() in response.lower() and len(prompt) > 20:
        format_score -= 10
    scores["format"] = max(0, min(format_score, 100))

    # 4. Coherence: no obvious gibberish
    coherence = 80
    repeated_chars = max(len(re.findall(r'(.)\1{5,}', response)), 0)
    if repeated_chars > 0:
        coherence -= repeated_chars * 10
    if response.count('?') > 5:
        coherence -= 10  # Too many questions = unsure
    scores["coherence"] = max(0, min(coherence, 100))

    # 5. Code quality (if code response expected)
    if any(kw in prompt.lower() for kw in ['code', 'python', 'function', 'script']):
        code_score = 50
        if '```' in response or 'def ' in response or 'import ' in response:
            code_score += 30
        if 'def ' in response:
            code_score += 10
        if 'return ' in response:
            code_score += 10
        scores["code_quality"] = min(code_score, 100)

    # Total
    weights = {"relevance": 0.3, "completeness": 0.25, "format": 0.2, "coherence": 0.25}
    total = sum(scores.get(k, 0) * w for k, w in weights.items()) / sum(weights.values())

    return {
        "scores": scores,
        "total": round(total, 1),
        "response_length": len(response),
        "response_words": response_length,
    }

def compare_responses(prompt: str, responses: dict) -> dict:
    """Compare les reponses de plusieurs noeuds."""
    evaluations = {}
    for node, response in responses.items():
        if isinstance(response, dict) and "error" in response:
            evaluations[node] = {"error": response["error"], "total": 0}
        else:
            text = response if isinstance(response, str) else str(response)
            evaluations[node] = score_response(prompt, text)

    # Rank
    ranked = sorted(evaluations.items(), key=lambda x: x[1].get("total", 0), reverse=True)

    return {
        "prompt": prompt[:100],
        "evaluations": evaluations,
        "ranking": [{"rank": i+1, "node": name, "score": ev.get("total", 0)}
                    for i, (name, ev) in enumerate(ranked)],
        "winner": ranked[0][0] if ranked else None,
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Response Evaluator — Qualite des reponses IA")
    parser.add_argument("--eval", nargs=2, metavar=("PROMPT", "RESPONSE"), help="Evaluer une reponse")
    parser.add_argument("--score", type=str, help="Scorer un texte (prompt auto)")
    parser.add_argument("--compare", type=str, help="Comparer tous les noeuds (requiert prompt_router)")
    parser.add_argument("--history", action="store_true", help="Historique")
    parser.add_argument("--leaderboard", action="store_true", help="Classement")
    args = parser.parse_args()

    db = init_db()

    if args.eval:
        result = score_response(args.eval[0], args.eval[1])
        # Store
        db.execute(
            "INSERT INTO evaluations (ts, prompt_preview, node, response_length, score_relevance, score_completeness, score_format, score_total, details) VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), args.eval[0][:100], "manual", len(args.eval[1]),
             result["scores"].get("relevance", 0), result["scores"].get("completeness", 0),
             result["scores"].get("format", 0), result["total"], json.dumps(result))
        )
        db.commit()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.score:
        result = score_response("general quality check", args.score)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.compare:
        # Import prompt_router for multi-node calls
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from prompt_router import call_node
            responses = {}
            for node in ["M1", "OL1-fast"]:
                r = call_node(node, args.compare)
                responses[node] = r.get("content", r.get("error", ""))
            result = compare_responses(args.compare, responses)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except ImportError:
            print(json.dumps({"error": "prompt_router.py requis pour --compare"}, ensure_ascii=False))

    elif args.history:
        rows = db.execute(
            "SELECT prompt_preview, node, score_total, ts FROM evaluations ORDER BY ts DESC LIMIT 20"
        ).fetchall()
        print(json.dumps([
            {"prompt": p[:50], "node": n, "score": s, "when": datetime.fromtimestamp(t).strftime("%H:%M")}
            for p, n, s, t in rows
        ], indent=2, ensure_ascii=False))

    elif args.leaderboard:
        rows = db.execute(
            "SELECT node, COUNT(*), AVG(score_total), MAX(score_total) FROM evaluations GROUP BY node ORDER BY 3 DESC"
        ).fetchall()
        print(json.dumps([
            {"node": n, "evals": c, "avg_score": round(a, 1), "best": round(m, 1)}
            for n, c, a, m in rows
        ], indent=2, ensure_ascii=False))

    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
