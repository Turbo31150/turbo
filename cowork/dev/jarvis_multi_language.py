#!/usr/bin/env python3
"""jarvis_multi_language.py — Simple multi-language detection and translation via M1.
COWORK #224 — Batch 102: JARVIS Conversational AI

Usage:
    python dev/jarvis_multi_language.py --detect "Bonjour le monde"
    python dev/jarvis_multi_language.py --translate "Hello world" --to fr
    python dev/jarvis_multi_language.py --supported
    python dev/jarvis_multi_language.py --stats
    python dev/jarvis_multi_language.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "multi_language.db"

# Language detection keyword sets
LANG_KEYWORDS = {
    "fr": {
        "keywords": ["le", "la", "les", "de", "du", "des", "un", "une", "est", "sont",
                      "dans", "pour", "avec", "sur", "pas", "que", "qui", "ce", "cette",
                      "mais", "ou", "et", "donc", "car", "nous", "vous", "ils", "elles",
                      "bonjour", "merci", "salut", "oui", "non", "comment", "pourquoi",
                      "je", "tu", "il", "elle", "mon", "ton", "son", "notre", "votre"],
        "name": "Francais",
        "name_en": "French"
    },
    "en": {
        "keywords": ["the", "is", "are", "was", "were", "have", "has", "had", "will",
                      "would", "could", "should", "can", "may", "might", "this", "that",
                      "these", "those", "with", "from", "into", "about", "between",
                      "hello", "please", "thank", "yes", "no", "how", "why", "what",
                      "which", "where", "when", "who", "not", "but", "and", "or"],
        "name": "English",
        "name_en": "English"
    },
    "es": {
        "keywords": ["el", "la", "los", "las", "de", "del", "un", "una", "es", "son",
                      "en", "con", "para", "por", "como", "que", "pero", "mas", "muy",
                      "hola", "gracias", "si", "no", "yo", "tu", "nosotros", "ellos",
                      "esta", "este", "eso", "donde", "cuando", "porque", "como"],
        "name": "Espanol",
        "name_en": "Spanish"
    },
    "de": {
        "keywords": ["der", "die", "das", "ein", "eine", "ist", "sind", "hat", "haben",
                      "mit", "von", "auf", "fur", "und", "oder", "aber", "nicht", "auch",
                      "hallo", "danke", "ja", "nein", "ich", "du", "er", "sie", "wir",
                      "kann", "wird", "war", "sehr", "gut", "bitte", "warum", "wie"],
        "name": "Deutsch",
        "name_en": "German"
    }
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        text_hash TEXT NOT NULL,
        text_preview TEXT,
        detected_lang TEXT NOT NULL,
        confidence REAL,
        scores TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS translations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        source_lang TEXT,
        target_lang TEXT NOT NULL,
        source_text TEXT NOT NULL,
        translated_text TEXT,
        method TEXT DEFAULT 'M1',
        cached INTEGER DEFAULT 0,
        duration_ms INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS translation_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_text_hash TEXT NOT NULL,
        source_lang TEXT,
        target_lang TEXT NOT NULL,
        translated_text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        hit_count INTEGER DEFAULT 0,
        UNIQUE(source_text_hash, target_lang)
    )""")
    db.commit()
    return db

def text_hash(text):
    import hashlib
    return hashlib.md5(text.strip().lower().encode()).hexdigest()[:16]

def detect_language(text):
    """Detect language by keyword frequency."""
    words = text.lower().split()
    word_set = set(words)
    scores = {}

    for lang, info in LANG_KEYWORDS.items():
        matches = word_set.intersection(set(info["keywords"]))
        score = len(matches) / max(len(words), 1)
        scores[lang] = round(score, 4)

    if scores:
        best_lang = max(scores, key=scores.get)
        confidence = scores[best_lang]
        # If confidence is very low, default to fr
        if confidence < 0.05:
            best_lang = "fr"
            confidence = 0.0
    else:
        best_lang = "fr"
        confidence = 0.0

    return best_lang, confidence, scores

def translate_via_m1(text, source_lang, target_lang):
    """Translate text via M1 (curl to LM Studio)."""
    lang_names = {k: v["name_en"] for k, v in LANG_KEYWORDS.items()}
    src_name = lang_names.get(source_lang, source_lang)
    tgt_name = lang_names.get(target_lang, target_lang)

    prompt = f"/nothink/nTranslate the following text from {src_name} to {tgt_name}. Return ONLY the translation, nothing else./n/nText: {text}"
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": prompt,
        "temperature": 0.2,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False
    })

    try:
        cmd = f'curl -s --max-time 30 http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=35, shell=True)
        elapsed_ms = int((time.time() - start) * 1000)

        if r.stdout.strip():
            data = json.loads(r.stdout)
            # Extract from output - last message type
            output = data.get("output", [])
            translated = ""
            for item in output:
                if item.get("type") == "message":
                    content = item.get("content", [])
                    for c in content:
                        if c.get("type") == "output_text":
                            translated = c.get("text", "")
            if not translated and output:
                # Fallback: try first content
                translated = str(output[-1].get("content", ""))
            return translated.strip(), elapsed_ms, "M1"
        return None, 0, "M1_error"
    except Exception as e:
        return None, 0, f"error:{str(e)[:50]}"

def do_detect(text):
    db = init_db()
    lang, confidence, scores = detect_language(text)
    lang_info = LANG_KEYWORDS.get(lang, {})
    th = text_hash(text)

    db.execute("INSERT INTO detections (ts, text_hash, text_preview, detected_lang, confidence, scores) VALUES (?,?,?,?,?,?)",
               (datetime.now().isoformat(), th, text[:100], lang, confidence, json.dumps(scores)))
    db.commit()

    result = {
        "action": "detect",
        "text_preview": text[:100],
        "detected_language": lang,
        "language_name": lang_info.get("name", lang),
        "confidence": confidence,
        "all_scores": scores,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_translate(text, target_lang):
    db = init_db()
    source_lang, _, _ = detect_language(text)
    th = text_hash(text)

    # Check cache
    cached = db.execute("SELECT translated_text FROM translation_cache WHERE source_text_hash=? AND target_lang=?",
                        (th, target_lang)).fetchone()
    if cached:
        db.execute("UPDATE translation_cache SET hit_count = hit_count + 1 WHERE source_text_hash=? AND target_lang=?",
                   (th, target_lang))
        db.execute("INSERT INTO translations (ts, source_lang, target_lang, source_text, translated_text, method, cached, duration_ms) VALUES (?,?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), source_lang, target_lang, text, cached[0], "cache", 1, 0))
        db.commit()
        result = {
            "action": "translate",
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_text": text,
            "translated_text": cached[0],
            "method": "cache",
            "cached": True,
            "ts": datetime.now().isoformat()
        }
        db.close()
        return result

    # Translate via M1
    translated, elapsed_ms, method = translate_via_m1(text, source_lang, target_lang)
    if translated:
        # Save to cache
        db.execute("INSERT OR REPLACE INTO translation_cache (source_text_hash, source_lang, target_lang, translated_text, created_at) VALUES (?,?,?,?,?)",
                   (th, source_lang, target_lang, translated, datetime.now().isoformat()))
    db.execute("INSERT INTO translations (ts, source_lang, target_lang, source_text, translated_text, method, cached, duration_ms) VALUES (?,?,?,?,?,?,?,?)",
               (datetime.now().isoformat(), source_lang, target_lang, text, translated, method, 0, elapsed_ms))
    db.commit()

    result = {
        "action": "translate",
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_text": text,
        "translated_text": translated,
        "method": method,
        "duration_ms": elapsed_ms,
        "cached": False,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_supported():
    langs = []
    for code, info in LANG_KEYWORDS.items():
        langs.append({
            "code": code,
            "name": info["name"],
            "name_en": info["name_en"],
            "keywords_count": len(info["keywords"])
        })
    return {
        "action": "supported",
        "languages": langs,
        "default": "fr",
        "total": len(langs),
        "ts": datetime.now().isoformat()
    }

def do_stats():
    db = init_db()
    total_detections = db.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    total_translations = db.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
    cache_size = db.execute("SELECT COUNT(*) FROM translation_cache").fetchone()[0]
    cache_hits = db.execute("SELECT SUM(hit_count) FROM translation_cache").fetchone()[0] or 0
    lang_dist = db.execute("SELECT detected_lang, COUNT(*) FROM detections GROUP BY detected_lang").fetchall()
    recent = db.execute("SELECT ts, source_lang, target_lang, method, cached FROM translations ORDER BY id DESC LIMIT 10").fetchall()

    result = {
        "action": "stats",
        "total_detections": total_detections,
        "total_translations": total_translations,
        "cache_entries": cache_size,
        "cache_hits": cache_hits,
        "language_distribution": {r[0]: r[1] for r in lang_dist},
        "recent_translations": [{"ts": r[0], "from": r[1], "to": r[2], "method": r[3], "cached": bool(r[4])} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    total_det = db.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    total_trans = db.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
    cache = db.execute("SELECT COUNT(*) FROM translation_cache").fetchone()[0]
    result = {
        "status": "ok",
        "total_detections": total_det,
        "total_translations": total_trans,
        "cache_entries": cache,
        "supported_languages": list(LANG_KEYWORDS.keys()),
        "default_language": "fr",
        "translation_method": "M1 (qwen3-8b via curl 127.0.0.1:1234)",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="JARVIS Multi-Language — COWORK #224")
    parser.add_argument("--detect", type=str, metavar="TEXT", help="Detect language of text")
    parser.add_argument("--translate", type=str, metavar="TEXT", help="Translate text")
    parser.add_argument("--to", type=str, default="fr", help="Target language code (default: fr)")
    parser.add_argument("--supported", action="store_true", help="List supported languages")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.detect:
        print(json.dumps(do_detect(args.detect), ensure_ascii=False, indent=2))
    elif args.translate:
        print(json.dumps(do_translate(args.translate, args.to), ensure_ascii=False, indent=2))
    elif args.supported:
        print(json.dumps(do_supported(), ensure_ascii=False, indent=2))
    elif args.stats:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
