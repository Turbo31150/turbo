#!/usr/bin/env python3
"""ia_teacher_student.py — AI teacher/student learning system with adaptive difficulty.
COWORK #227 — Batch 103: IA Collaborative

Usage:
    python dev/ia_teacher_student.py --teach "Python decorators"
    python dev/ia_teacher_student.py --quiz
    python dev/ia_teacher_student.py --evaluate
    python dev/ia_teacher_student.py --progress
    python dev/ia_teacher_student.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "teacher_student.db"

DIFFICULTY_LEVELS = ["debutant", "intermediaire", "avance", "expert"]

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        topic TEXT NOT NULL,
        difficulty TEXT DEFAULT 'intermediaire',
        content TEXT NOT NULL,
        teacher_model TEXT DEFAULT 'M1',
        duration_ms INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER,
        ts TEXT NOT NULL,
        topic TEXT NOT NULL,
        question TEXT NOT NULL,
        expected_answer TEXT,
        student_answer TEXT,
        student_model TEXT DEFAULT 'OL1',
        correct INTEGER,
        score REAL,
        difficulty TEXT,
        FOREIGN KEY (lesson_id) REFERENCES lessons(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE NOT NULL,
        lessons_count INTEGER DEFAULT 0,
        quizzes_count INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        current_difficulty TEXT DEFAULT 'debutant',
        avg_score REAL DEFAULT 0,
        last_activity TEXT
    )""")
    db.commit()
    return db

def query_m1(prompt):
    payload = json.dumps({
        "model": "qwen3-8b",
        "input": f"/nothink/n{prompt}",
        "temperature": 0.3,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:1234/api/v1/chat -H "Content-Type: application/json" -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "").strip(), elapsed
        return None, elapsed
    except Exception:
        return None, 0

def query_ol1(prompt):
    payload = json.dumps({
        "model": "qwen3:1.7b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    })
    try:
        cmd = f'curl -s --max-time 60 http://127.0.0.1:11434/api/chat -d {json.dumps(payload)}'
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=65, shell=True)
        elapsed = int((time.time() - start) * 1000)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            content = data.get("message", {}).get("content", "")
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content.strip(), elapsed
        return None, elapsed
    except Exception:
        return None, 0

def get_topic_difficulty(db, topic):
    row = db.execute("SELECT current_difficulty FROM progress WHERE topic=?", (topic,)).fetchone()
    return row[0] if row else "debutant"

def update_progress(db, topic, correct=None):
    row = db.execute("SELECT * FROM progress WHERE topic=?", (topic,)).fetchone()
    now = datetime.now().isoformat()
    if not row:
        db.execute("INSERT INTO progress (topic, lessons_count, quizzes_count, correct_count, current_difficulty, last_activity) VALUES (?,?,?,?,?,?)",
                   (topic, 1, 0, 0, "debutant", now))
    else:
        if correct is not None:
            new_quiz = (row[3] or 0) + 1
            new_correct = (row[4] or 0) + (1 if correct else 0)
            avg = new_correct / new_quiz if new_quiz > 0 else 0
            # Adaptive difficulty
            diff = row[5] or "debutant"
            idx = DIFFICULTY_LEVELS.index(diff) if diff in DIFFICULTY_LEVELS else 0
            if avg >= 0.8 and new_quiz >= 3 and idx < len(DIFFICULTY_LEVELS) - 1:
                diff = DIFFICULTY_LEVELS[idx + 1]
            elif avg < 0.4 and new_quiz >= 3 and idx > 0:
                diff = DIFFICULTY_LEVELS[idx - 1]
            db.execute("UPDATE progress SET quizzes_count=?, correct_count=?, avg_score=?, current_difficulty=?, last_activity=? WHERE topic=?",
                       (new_quiz, new_correct, round(avg, 3), diff, now, topic))
        else:
            db.execute("UPDATE progress SET lessons_count = lessons_count + 1, last_activity=? WHERE topic=?", (now, topic))
    db.commit()

def do_teach(topic):
    db = init_db()
    difficulty = get_topic_difficulty(db, topic)

    prompt = f"Tu es un professeur expert. Enseigne le sujet: '{topic}' au niveau {difficulty}.\nStructure: 1) Introduction 2) Concepts cles 3) Exemple pratique 4) Resume\nSois pedagogique, concis (300 mots max)."

    lesson, elapsed = query_m1(prompt)
    if lesson:
        db.execute("INSERT INTO lessons (ts, topic, difficulty, content, teacher_model, duration_ms) VALUES (?,?,?,?,?,?)",
                   (datetime.now().isoformat(), topic, difficulty, lesson, "M1", elapsed))
        update_progress(db, topic)
        db.commit()

    result = {
        "action": "teach",
        "topic": topic,
        "difficulty": difficulty,
        "lesson": lesson[:1500] if lesson else "M1 teacher unavailable",
        "teacher_model": "M1 (qwen3-8b)",
        "duration_ms": elapsed,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_quiz():
    db = init_db()
    # Get last lesson topic
    lesson = db.execute("SELECT id, topic, difficulty, content FROM lessons ORDER BY id DESC LIMIT 1").fetchone()
    if not lesson:
        db.close()
        return {"error": "No lessons found. Use --teach first."}

    lesson_id, topic, difficulty, content = lesson

    # M1 generates question
    q_prompt = f"Base sur cette lecon sur '{topic}' (niveau {difficulty}), genere UNE question technique avec sa reponse attendue.\nLecon: {content[:500]}\nFormat:\nQUESTION: [question]\nREPONSE_ATTENDUE: [reponse]"
    q_text, q_ms = query_m1(q_prompt)

    question = q_text[:500] if q_text else f"Explique le concept principal de {topic}"
    expected = ""
    if q_text and "REPONSE_ATTENDUE:" in q_text:
        parts = q_text.split("REPONSE_ATTENDUE:")
        question = parts[0].replace("QUESTION:", "").strip()
        expected = parts[1].strip()

    # OL1 (student) answers
    s_prompt = f"Reponds a cette question sur '{topic}':\n{question}\nSois precis et concis."
    student_answer, s_ms = query_ol1(s_prompt)

    # M1 evaluates
    eval_prompt = f"Evalue cette reponse (score 0-10):\nQuestion: {question}\nReponse attendue: {expected}\nReponse etudiante: {student_answer}\nFormat: SCORE: X/10 CORRECT: oui/non FEEDBACK: [feedback]"
    eval_text, e_ms = query_m1(eval_prompt)

    correct = False
    score = 5.0
    if eval_text:
        if "CORRECT: oui" in eval_text.lower() or "correct: oui" in eval_text.lower():
            correct = True
        import re
        score_match = re.search(r'SCORE:\s*(\d+)', eval_text, re.IGNORECASE)
        if score_match:
            score = float(score_match.group(1))

    db.execute("""INSERT INTO quizzes (lesson_id, ts, topic, question, expected_answer, student_answer, student_model, correct, score, difficulty)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
               (lesson_id, datetime.now().isoformat(), topic, question[:500], expected[:500],
                student_answer[:500] if student_answer else None, "OL1", int(correct), score, difficulty))
    update_progress(db, topic, correct)
    db.commit()

    result = {
        "action": "quiz",
        "topic": topic,
        "difficulty": difficulty,
        "question": question[:500],
        "expected_answer": expected[:300],
        "student_answer": student_answer[:500] if student_answer else "OL1 unavailable",
        "evaluation": eval_text[:500] if eval_text else "Evaluation unavailable",
        "correct": correct,
        "score": score,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_evaluate():
    db = init_db()
    recent = db.execute("SELECT topic, correct, score, difficulty FROM quizzes ORDER BY id DESC LIMIT 20").fetchall()
    if not recent:
        db.close()
        return {"action": "evaluate", "message": "No quizzes to evaluate"}

    total = len(recent)
    correct = sum(1 for r in recent if r[1])
    avg_score = sum(r[2] for r in recent) / total

    result = {
        "action": "evaluate",
        "quizzes_evaluated": total,
        "correct": correct,
        "accuracy": round(correct / total, 3),
        "avg_score": round(avg_score, 1),
        "by_difficulty": {},
        "ts": datetime.now().isoformat()
    }

    for diff in DIFFICULTY_LEVELS:
        diff_quizzes = [r for r in recent if r[3] == diff]
        if diff_quizzes:
            result["by_difficulty"][diff] = {
                "count": len(diff_quizzes),
                "correct": sum(1 for r in diff_quizzes if r[1]),
                "avg_score": round(sum(r[2] for r in diff_quizzes) / len(diff_quizzes), 1)
            }
    db.close()
    return result

def do_progress():
    db = init_db()
    rows = db.execute("SELECT topic, lessons_count, quizzes_count, correct_count, current_difficulty, avg_score, last_activity FROM progress ORDER BY last_activity DESC").fetchall()
    topics = []
    for r in rows:
        topics.append({
            "topic": r[0], "lessons": r[1], "quizzes": r[2], "correct": r[3],
            "difficulty": r[4], "avg_score": round(r[5] or 0, 3), "last_activity": r[6]
        })
    result = {
        "action": "progress",
        "topics": topics,
        "total_topics": len(topics),
        "difficulty_levels": DIFFICULTY_LEVELS,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    lessons = db.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    quizzes = db.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
    topics = db.execute("SELECT COUNT(*) FROM progress").fetchone()[0]
    avg = db.execute("SELECT AVG(score) FROM quizzes").fetchone()[0] or 0
    result = {
        "status": "ok",
        "total_lessons": lessons,
        "total_quizzes": quizzes,
        "topics_tracked": topics,
        "avg_quiz_score": round(avg, 1),
        "teacher_model": "M1 (qwen3-8b)",
        "student_model": "OL1 (qwen3:1.7b)",
        "difficulty_levels": DIFFICULTY_LEVELS,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="IA Teacher/Student — COWORK #227")
    parser.add_argument("--teach", type=str, metavar="TOPIC", help="Teach a topic")
    parser.add_argument("--quiz", action="store_true", help="Quiz on last lesson")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate recent quizzes")
    parser.add_argument("--progress", action="store_true", help="Show learning progress")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.teach:
        print(json.dumps(do_teach(args.teach), ensure_ascii=False, indent=2))
    elif args.quiz:
        print(json.dumps(do_quiz(), ensure_ascii=False, indent=2))
    elif args.evaluate:
        print(json.dumps(do_evaluate(), ensure_ascii=False, indent=2))
    elif args.progress:
        print(json.dumps(do_progress(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
