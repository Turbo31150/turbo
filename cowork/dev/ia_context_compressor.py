#!/usr/bin/env python3
"""ia_context_compressor.py — Compression de contexte IA.

Resume les longs contextes pour rester dans les limites tokens.

Usage:
    python dev/ia_context_compressor.py --once
    python dev/ia_context_compressor.py --compress "TEXTE LONG"
    python dev/ia_context_compressor.py --ratio
    python dev/ia_context_compressor.py --evaluate
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "context_compressor.db"
M1_URL = "http://127.0.0.1:1234/api/v1/chat"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS compressions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, original_len INTEGER, compressed_len INTEGER,
        ratio REAL, passes INTEGER, keywords_preserved REAL)""")
    db.commit()
    return db


def query_m1(prompt, timeout=20):
    """Query M1 for compression."""
    try:
        data = json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.2, "max_output_tokens": 1024, "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            for item in reversed(result.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
    except Exception:
        pass
    return ""


def extract_keywords(text, top_n=20):
    """Extract important keywords from text."""
    import re
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{3,}', text.lower())
    # Filter common words
    stop = {"this", "that", "with", "from", "have", "been", "will", "would", "could",
            "should", "there", "their", "about", "which", "when", "what", "your"}
    filtered = [w for w in words if w not in stop]

    # Count frequency
    freq = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    return sorted(freq.keys(), key=lambda x: freq[x], reverse=True)[:top_n]


def compress_text(text, target_ratio=0.5, max_passes=3):
    """Compress text iteratively."""
    original_len = len(text)
    original_keywords = set(extract_keywords(text))
    current = text
    passes = 0

    for i in range(max_passes):
        if len(current) <= original_len * target_ratio:
            break

        prompt = f"""Resume ce texte en conservant TOUS les faits cles, chiffres et termes techniques.
Reduis la longueur de 50%. Pas d'introduction ni de conclusion, juste le contenu condense.

TEXTE:
{current[:3000]}"""

        compressed = query_m1(prompt)
        if compressed and len(compressed) < len(current):
            current = compressed
            passes += 1
        else:
            break

    # Evaluate keyword preservation
    compressed_keywords = set(extract_keywords(current))
    preserved = len(original_keywords & compressed_keywords) / max(len(original_keywords), 1)

    return {
        "compressed": current,
        "original_len": original_len,
        "compressed_len": len(current),
        "ratio": round(len(current) / max(original_len, 1), 3),
        "passes": passes,
        "keywords_preserved": round(preserved, 3),
    }


def do_compress(text=None):
    """Run compression."""
    db = init_db()

    if not text:
        # Demo text
        text = """JARVIS est un systeme d'assistant IA autonome deploye sur Windows 11 avec un cluster de 10 GPU
totalisant 78 GB de VRAM. Le systeme utilise 3 serveurs LM Studio (M1 avec qwen3-8b sur 6 GPU 46GB,
M2 avec deepseek-r1 sur 3 GPU 24GB, M3 avec deepseek-r1 sur 1 GPU 8GB) plus Ollama avec
qwen3:1.7b local. L'architecture comprend 192+ outils MCP,
89 skills, 2341 commandes vocales, 79 scripts COWORK, et 551 tests. Le pipeline vocal utilise
OpenWakeWord avec Whisper large-v3-turbo CUDA et TTS Edge fr-FR-HenriNeural avec latence <2s."""

    result = compress_text(text)

    db.execute(
        "INSERT INTO compressions (ts, original_len, compressed_len, ratio, passes, keywords_preserved) VALUES (?,?,?,?,?,?)",
        (time.time(), result["original_len"], result["compressed_len"],
         result["ratio"], result["passes"], result["keywords_preserved"])
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "original_len": result["original_len"],
        "compressed_len": result["compressed_len"],
        "compression_ratio": result["ratio"],
        "passes": result["passes"],
        "keywords_preserved_pct": result["keywords_preserved"],
        "preview": result["compressed"][:300],
    }


def show_ratios():
    """Show compression history."""
    db = init_db()
    rows = db.execute(
        "SELECT ts, original_len, compressed_len, ratio, keywords_preserved FROM compressions ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    db.close()
    return [{
        "ts": datetime.fromtimestamp(r[0]).isoformat(),
        "original": r[1], "compressed": r[2],
        "ratio": r[3], "keywords": r[4],
    } for r in rows]


def main():
    parser = argparse.ArgumentParser(description="IA Context Compressor")
    parser.add_argument("--once", action="store_true", help="Demo compression")
    parser.add_argument("--compress", metavar="TEXT", help="Compress text")
    parser.add_argument("--ratio", action="store_true", help="Show ratios")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate quality")
    args = parser.parse_args()

    if args.ratio:
        print(json.dumps(show_ratios(), ensure_ascii=False, indent=2))
    else:
        result = do_compress(args.compress)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
