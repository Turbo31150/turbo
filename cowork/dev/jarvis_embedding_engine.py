#!/usr/bin/env python3
"""jarvis_embedding_engine.py — Moteur embedding JARVIS.

Vectorise tous les scripts pour recherche semantique TF-IDF.

Usage:
    python dev/jarvis_embedding_engine.py --once
    python dev/jarvis_embedding_engine.py --index
    python dev/jarvis_embedding_engine.py --search "QUERY"
    python dev/jarvis_embedding_engine.py --stats
"""
import argparse
import json
import math
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "embedding_engine.db"
STOPWORDS = {"the", "and", "for", "that", "this", "with", "from", "are", "was", "not",
             "but", "all", "can", "had", "her", "one", "our", "out", "you", "def",
             "import", "self", "none", "true", "false", "return", "class", "pass",
             "les", "des", "une", "dans", "pour", "sur", "par", "est", "qui", "que"}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, filepath TEXT UNIQUE, tokens TEXT, doc_len INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, query TEXT, results_count INTEGER)""")
    db.commit()
    return db


def tokenize(text):
    words = re.findall(r'[a-z_]{3,}', text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) < 30]


def build_index():
    db = init_db()
    docs = {}
    df = Counter()  # Document frequency

    for py in sorted(DEV.glob("*.py")):
        try:
            content = py.read_text(encoding="utf-8", errors="replace")
            tokens = tokenize(content)
            tf = Counter(tokens)
            docs[py.name] = {"tf": dict(tf), "len": len(tokens)}
            for word in set(tokens):
                df[word] += 1
            db.execute("INSERT OR REPLACE INTO documents (ts, filepath, tokens, doc_len) VALUES (?,?,?,?)",
                       (time.time(), py.name, json.dumps(dict(tf.most_common(50))), len(tokens)))
        except Exception:
            pass

    db.commit()
    db.close()
    return docs, df


def cosine_sim(v1, v2):
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def search(query, top_k=10):
    docs, df = build_index()
    n_docs = len(docs)
    query_tokens = tokenize(query)
    query_tf = Counter(query_tokens)

    # TF-IDF for query
    query_vec = {}
    for word, count in query_tf.items():
        idf = math.log(n_docs / (1 + df.get(word, 0)))
        query_vec[word] = count * idf

    results = []
    for name, info in docs.items():
        doc_vec = {}
        for word, count in info["tf"].items():
            idf = math.log(n_docs / (1 + df.get(word, 0)))
            doc_vec[word] = count * idf
        sim = cosine_sim(query_vec, doc_vec)
        if sim > 0.01:
            results.append({"file": name, "score": round(sim, 4), "tokens": info["len"]})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def do_index():
    docs, df = build_index()
    return {
        "ts": datetime.now().isoformat(),
        "documents_indexed": len(docs),
        "unique_terms": len(df),
        "top_terms": dict(df.most_common(20)),
        "avg_doc_length": round(sum(d["len"] for d in docs.values()) / max(len(docs), 1)),
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Embedding Engine")
    parser.add_argument("--once", "--index", action="store_true", help="Build index")
    parser.add_argument("--search", metavar="QUERY", help="Search query")
    parser.add_argument("--similar", metavar="FILE", help="Find similar")
    parser.add_argument("--stats", action="store_true", help="Index stats")
    args = parser.parse_args()

    if args.search:
        results = search(args.search)
        print(json.dumps({"query": args.search, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_index(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
