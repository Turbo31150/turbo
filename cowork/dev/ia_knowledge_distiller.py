#!/usr/bin/env python3
"""ia_knowledge_distiller.py (#188) — Extraction et condensation de connaissances.

Interroge M1 et OL1 en parallele, fusionne les reponses, extrait les faits cles,
genere des quiz de verification.

Usage:
    python dev/ia_knowledge_distiller.py --once
    python dev/ia_knowledge_distiller.py --distill "Python asyncio"
    python dev/ia_knowledge_distiller.py --quiz "Python asyncio"
    python dev/ia_knowledge_distiller.py --verify "Python asyncio"
    python dev/ia_knowledge_distiller.py --export
"""
import argparse
import json
import re
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "knowledge_distiller.db"

M1_URL = "http://127.0.0.1:1234/api/v1/chat"
M1_MODEL = "qwen3-8b"
OL1_URL = "http://127.0.0.1:11434/api/chat"
OL1_MODEL = "qwen3:1.7b"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        topic TEXT,
        key_facts_json TEXT,
        sources_json TEXT,
        fact_count INTEGER,
        m1_response TEXT,
        ol1_response TEXT,
        merged_summary TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        topic TEXT,
        knowledge_id INTEGER,
        questions_json TEXT,
        answers_json TEXT,
        question_count INTEGER,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        topic TEXT,
        knowledge_id INTEGER,
        verified INTEGER DEFAULT 0,
        discrepancies_json TEXT,
        confidence REAL,
        FOREIGN KEY (knowledge_id) REFERENCES knowledge(id)
    )""")
    db.commit()
    return db


def query_m1(prompt, max_tokens=2048):
    """Query M1 via curl."""
    payload = json.dumps({
        "model": M1_MODEL,
        "input": f"/nothink\n{prompt}",
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
        "stream": False,
        "store": False
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "60", M1_URL,
             "-H", "Content-Type: application/json", "-d", payload],
            capture_output=True, text=True, timeout=65
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "")
        return None
    except Exception:
        return None


def query_ol1(prompt, max_tokens=2048):
    """Query OL1 via curl."""
    payload = json.dumps({
        "model": OL1_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "30", OL1_URL,
             "-d", payload],
            capture_output=True, text=True, timeout=35
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        return data.get("message", {}).get("content", None)
    except Exception:
        return None


def query_parallel(prompt_m1, prompt_ol1):
    """Query M1 and OL1 in parallel."""
    results = {"m1": None, "ol1": None}

    def run_m1():
        results["m1"] = query_m1(prompt_m1)

    def run_ol1():
        results["ol1"] = query_ol1(prompt_ol1)

    t1 = threading.Thread(target=run_m1)
    t2 = threading.Thread(target=run_ol1)
    t1.start()
    t2.start()
    t1.join(timeout=70)
    t2.join(timeout=40)
    return results


def extract_bullet_points(text):
    """Extract bullet point facts from text."""
    if not text:
        return []
    facts = []
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        # Match bullet points, numbered items
        match = re.match(r'^(?:[-*+]|\d+[.)])\s*(.+)', line)
        if match:
            fact = match.group(1).strip()
            if len(fact) > 10:
                facts.append(fact)
        elif len(line) > 20 and not line.startswith("#"):
            # Include substantial lines as facts too
            if ":" in line or line.endswith("."):
                facts.append(line)
    # Deduplicate similar facts
    seen = set()
    unique = []
    for f in facts:
        key = f.lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique[:20]


def merge_facts(m1_facts, ol1_facts):
    """Merge facts from both sources, removing duplicates."""
    all_facts = []
    seen_keys = set()
    for fact in m1_facts + ol1_facts:
        key = re.sub(r'[^a-z0-9]', '', fact.lower())[:40]
        if key not in seen_keys and len(key) > 5:
            seen_keys.add(key)
            all_facts.append(fact)
    return all_facts


def distill_topic(db, topic):
    """Distill knowledge on a topic from M1 and OL1."""
    prompt = (
        f"List the key facts about: {topic}\n\n"
        "Format your answer as bullet points (- fact). "
        "Include definitions, key concepts, best practices, and important details. "
        "Be precise and concise. 10-15 bullet points."
    )

    results = query_parallel(prompt, prompt)
    m1_text = results["m1"] or ""
    ol1_text = results["ol1"] or ""

    m1_facts = extract_bullet_points(m1_text)
    ol1_facts = extract_bullet_points(ol1_text)
    merged = merge_facts(m1_facts, ol1_facts)

    sources = []
    if m1_text:
        sources.append("M1/qwen3-8b")
    if ol1_text:
        sources.append("OL1/qwen3:1.7b")

    # Generate summary from M1
    summary = ""
    if merged:
        summary_prompt = (
            f"Summarize these key facts about '{topic}' in 2-3 sentences:\n"
            + "\n".join(f"- {f}" for f in merged[:10])
        )
        summary = query_m1(summary_prompt, max_tokens=512) or ""

    db.execute(
        """INSERT INTO knowledge
           (ts, topic, key_facts_json, sources_json, fact_count,
            m1_response, ol1_response, merged_summary)
           VALUES (?,?,?,?,?,?,?,?)""",
        (time.time(), topic, json.dumps(merged, ensure_ascii=False),
         json.dumps(sources), len(merged),
         m1_text[:2000], ol1_text[:2000], summary[:1000])
    )
    db.commit()

    return {
        "status": "ok",
        "topic": topic,
        "fact_count": len(merged),
        "sources": sources,
        "key_facts": merged,
        "summary": summary[:500],
        "m1_contributed": len(m1_facts),
        "ol1_contributed": len(ol1_facts)
    }


def generate_quiz(db, topic):
    """Generate a quiz from stored knowledge on topic."""
    row = db.execute(
        "SELECT id, key_facts_json FROM knowledge WHERE topic = ? ORDER BY ts DESC LIMIT 1",
        (topic,)
    ).fetchone()

    if not row:
        # Distill first
        distill_topic(db, topic)
        row = db.execute(
            "SELECT id, key_facts_json FROM knowledge WHERE topic = ? ORDER BY ts DESC LIMIT 1",
            (topic,)
        ).fetchone()

    if not row:
        return {"status": "error", "error": "Could not distill knowledge for quiz"}

    kid, facts_json = row
    facts = json.loads(facts_json)

    prompt = (
        f"Based on these facts about '{topic}':\n"
        + "\n".join(f"- {f}" for f in facts[:10])
        + "\n\nGenerate 5 quiz questions with answers. "
        "Format as JSON array: [{\"q\": \"question?\", \"a\": \"answer\"}]"
    )
    raw = query_m1(prompt, max_tokens=1024)
    questions = []
    answers = []

    if raw:
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                qa_list = json.loads(match.group())
                for qa in qa_list[:5]:
                    if isinstance(qa, dict):
                        questions.append(qa.get("q", qa.get("question", "")))
                        answers.append(qa.get("a", qa.get("answer", "")))
        except (json.JSONDecodeError, ValueError):
            pass

    if not questions:
        # Fallback: generate from facts
        for i, fact in enumerate(facts[:5]):
            questions.append(f"What is true about {topic} regarding: {fact[:50]}...?")
            answers.append(fact)

    db.execute(
        """INSERT INTO quizzes (ts, topic, knowledge_id, questions_json, answers_json, question_count)
           VALUES (?,?,?,?,?,?)""",
        (time.time(), topic, kid,
         json.dumps(questions, ensure_ascii=False),
         json.dumps(answers, ensure_ascii=False),
         len(questions))
    )
    db.commit()

    return {
        "status": "ok",
        "topic": topic,
        "question_count": len(questions),
        "quiz": [{"q": q, "a": a} for q, a in zip(questions, answers)]
    }


def verify_knowledge(db, topic):
    """Verify stored knowledge by cross-checking with fresh queries."""
    row = db.execute(
        "SELECT id, key_facts_json FROM knowledge WHERE topic = ? ORDER BY ts DESC LIMIT 1",
        (topic,)
    ).fetchone()

    if not row:
        return {"status": "error", "error": f"No knowledge stored for '{topic}'. Use --distill first."}

    kid, facts_json = row
    facts = json.loads(facts_json)

    prompt = (
        f"Verify these facts about '{topic}'. For each, say TRUE or FALSE with a brief reason.\n"
        + "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts[:8]))
        + "\n\nReply as JSON array: [{\"fact\": \"...\", \"valid\": true/false, \"reason\": \"...\"}]"
    )
    raw = query_m1(prompt, max_tokens=1024)
    discrepancies = []
    verified_count = 0

    if raw:
        try:
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                items = json.loads(match.group())
                for item in items:
                    if isinstance(item, dict):
                        if item.get("valid", True):
                            verified_count += 1
                        else:
                            discrepancies.append({
                                "fact": item.get("fact", ""),
                                "reason": item.get("reason", "")
                            })
        except (json.JSONDecodeError, ValueError):
            verified_count = len(facts)

    confidence = round(verified_count / max(len(facts), 1) * 100, 1)

    db.execute(
        """INSERT INTO verifications (ts, topic, knowledge_id, verified, discrepancies_json, confidence)
           VALUES (?,?,?,?,?,?)""",
        (time.time(), topic, kid, verified_count,
         json.dumps(discrepancies, ensure_ascii=False), confidence)
    )
    db.commit()

    return {
        "status": "ok",
        "topic": topic,
        "total_facts": len(facts),
        "verified": verified_count,
        "discrepancies": len(discrepancies),
        "confidence": confidence,
        "issues": discrepancies
    }


def export_all(db):
    """Export all knowledge."""
    rows = db.execute(
        "SELECT topic, key_facts_json, sources_json, fact_count, merged_summary, ts "
        "FROM knowledge ORDER BY ts DESC"
    ).fetchall()
    return {
        "status": "ok",
        "total_topics": len(rows),
        "knowledge": [
            {
                "topic": r[0],
                "facts": json.loads(r[1]),
                "sources": json.loads(r[2]),
                "fact_count": r[3],
                "summary": r[4],
                "ts": datetime.fromtimestamp(r[5]).strftime("%Y-%m-%d %H:%M:%S")
            }
            for r in rows
        ]
    }


def once(db):
    """Run once with demo."""
    total_topics = db.execute("SELECT COUNT(DISTINCT topic) FROM knowledge").fetchone()[0]
    total_facts = db.execute("SELECT COALESCE(SUM(fact_count), 0) FROM knowledge").fetchone()[0]
    total_quizzes = db.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]

    demo = distill_topic(db, "SQLite database")

    return {
        "status": "ok",
        "mode": "once",
        "script": "ia_knowledge_distiller.py (#188)",
        "stats": {
            "total_topics": total_topics + 1,
            "total_facts": total_facts + demo["fact_count"],
            "total_quizzes": total_quizzes
        },
        "demo": demo
    }


def main():
    parser = argparse.ArgumentParser(
        description="ia_knowledge_distiller.py (#188) — Extraction et condensation de connaissances"
    )
    parser.add_argument("--distill", type=str, metavar="TOPIC",
                        help="Distill knowledge on a topic from M1+OL1")
    parser.add_argument("--quiz", type=str, metavar="TOPIC",
                        help="Generate quiz questions on a topic")
    parser.add_argument("--verify", type=str, metavar="TOPIC",
                        help="Verify stored knowledge with fresh cross-check")
    parser.add_argument("--export", action="store_true",
                        help="Export all stored knowledge as JSON")
    parser.add_argument("--once", action="store_true",
                        help="Run once with demo distillation")
    args = parser.parse_args()

    db = init_db()

    if args.distill:
        result = distill_topic(db, args.distill)
    elif args.quiz:
        result = generate_quiz(db, args.quiz)
    elif args.verify:
        result = verify_knowledge(db, args.verify)
    elif args.export:
        result = export_all(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
