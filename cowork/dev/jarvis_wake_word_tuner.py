#!/usr/bin/env python3
"""jarvis_wake_word_tuner.py — Wake word sensitivity tuner for OpenWakeWord.
COWORK #231 — Batch 105: JARVIS Voice 2.0

Usage:
    python dev/jarvis_wake_word_tuner.py --test
    python dev/jarvis_wake_word_tuner.py --sensitivity 0.7
    python dev/jarvis_wake_word_tuner.py --false-positives
    python dev/jarvis_wake_word_tuner.py --calibrate
    python dev/jarvis_wake_word_tuner.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "wake_word_tuner.db"

SIMILAR_PHRASES = [
    "jarvis", "service", "avis", "paris", "garvis", "tarvis",
    "jardin", "larvae", "harvest", "jarvice", "jarvid",
    "charles", "marvis", "darvis", "narvis"
]

SENSITIVITY_PRESETS = {
    "strict": {"threshold": 0.85, "description": "Fewer false positives, may miss quiet activations"},
    "balanced": {"threshold": 0.70, "description": "Default — good balance of sensitivity and accuracy"},
    "sensitive": {"threshold": 0.55, "description": "More responsive, higher false positive rate"},
    "ultra": {"threshold": 0.40, "description": "Maximum sensitivity, many false positives expected"},
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS sensitivity_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        threshold REAL NOT NULL,
        preset TEXT,
        reason TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS wake_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        phrase TEXT NOT NULL,
        expected_wake INTEGER NOT NULL,
        would_trigger INTEGER,
        threshold REAL,
        confidence REAL,
        test_type TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS false_positive_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        trigger_phrase TEXT,
        confidence REAL,
        threshold REAL,
        was_false_positive INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS calibration_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        phrases_tested INTEGER,
        true_positives INTEGER,
        false_positives INTEGER,
        true_negatives INTEGER,
        false_negatives INTEGER,
        accuracy REAL,
        recommended_threshold REAL
    )""")
    db.commit()
    return db

def get_current_threshold(db):
    row = db.execute("SELECT threshold, preset FROM sensitivity_config ORDER BY id DESC LIMIT 1").fetchone()
    return (row[0], row[1]) if row else (0.70, "balanced")

def simulate_wake_detection(phrase, threshold):
    """Simulate wake word detection based on string similarity to 'jarvis'."""
    target = "jarvis"
    phrase_lower = phrase.lower().strip()

    # Simple similarity score based on character overlap and position
    if phrase_lower == target:
        confidence = 0.98
    elif target in phrase_lower:
        confidence = 0.90
    else:
        # Levenshtein-like similarity
        matches = 0
        for i, ch in enumerate(phrase_lower[:len(target)]):
            if i < len(target) and ch == target[i]:
                matches += 1
        base_sim = matches / max(len(target), len(phrase_lower))

        # Phonetic bonus for similar sounding
        phonetic_similar = ["arvis", "arvi", "jarv", "jervis", "jarvice"]
        phonetic_bonus = 0.15 if any(p in phrase_lower for p in phonetic_similar) else 0

        confidence = min(0.95, base_sim + phonetic_bonus)

    would_trigger = confidence >= threshold
    return confidence, would_trigger

def do_test():
    db = init_db()
    threshold, preset = get_current_threshold(db)
    results = []

    for phrase in SIMILAR_PHRASES:
        expected = phrase.lower() == "jarvis"
        confidence, would_trigger = simulate_wake_detection(phrase, threshold)
        correct = (would_trigger == expected)

        db.execute("INSERT INTO wake_tests (ts, phrase, expected_wake, would_trigger, threshold, confidence, test_type) VALUES (?,?,?,?,?,?,?)",
                   (datetime.now().isoformat(), phrase, int(expected), int(would_trigger), threshold, confidence, "similarity_test"))

        results.append({
            "phrase": phrase,
            "expected": expected,
            "would_trigger": would_trigger,
            "confidence": round(confidence, 3),
            "correct": correct
        })

    db.commit()
    correct_count = sum(1 for r in results if r["correct"])
    accuracy = correct_count / len(results) if results else 0

    result = {
        "action": "test",
        "threshold": threshold,
        "preset": preset,
        "phrases_tested": len(results),
        "accuracy": round(accuracy, 3),
        "correct": correct_count,
        "incorrect": len(results) - correct_count,
        "details": results,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_sensitivity(value):
    db = init_db()
    value = max(0.1, min(1.0, value))
    preset = "custom"
    for name, info in SENSITIVITY_PRESETS.items():
        if abs(info["threshold"] - value) < 0.05:
            preset = name
            break

    db.execute("INSERT INTO sensitivity_config (ts, threshold, preset, reason) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), value, preset, "manual_set"))
    db.commit()

    result = {
        "action": "set_sensitivity",
        "threshold": value,
        "preset": preset,
        "presets_available": {k: v["threshold"] for k, v in SENSITIVITY_PRESETS.items()},
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_false_positives():
    db = init_db()
    total = db.execute("SELECT COUNT(*) FROM false_positive_log").fetchone()[0]
    recent = db.execute("SELECT ts, trigger_phrase, confidence, threshold FROM false_positive_log ORDER BY id DESC LIMIT 20").fetchall()
    # Also check from wake_tests
    fp_tests = db.execute("""SELECT phrase, confidence, threshold FROM wake_tests
                            WHERE expected_wake=0 AND would_trigger=1 ORDER BY id DESC LIMIT 10""").fetchall()

    result = {
        "action": "false_positives",
        "total_logged": total,
        "recent_false_positives": [{"ts": r[0], "phrase": r[1], "confidence": r[2], "threshold": r[3]} for r in recent],
        "test_false_positives": [{"phrase": r[0], "confidence": round(r[1], 3), "threshold": r[2]} for r in fp_tests],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_calibrate():
    db = init_db()
    best_accuracy = 0
    best_threshold = 0.7

    thresholds_to_test = [0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]
    calibration_results = []

    for t in thresholds_to_test:
        tp = fp = tn = fn = 0
        for phrase in SIMILAR_PHRASES:
            expected = phrase.lower() == "jarvis"
            confidence, would_trigger = simulate_wake_detection(phrase, t)
            if expected and would_trigger:
                tp += 1
            elif expected and not would_trigger:
                fn += 1
            elif not expected and would_trigger:
                fp += 1
            else:
                tn += 1

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        calibration_results.append({
            "threshold": t, "accuracy": round(accuracy, 3),
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3), "tp": tp, "fp": fp, "tn": tn, "fn": fn
        })

        if f1 > best_accuracy:
            best_accuracy = f1
            best_threshold = t

    # Save calibration
    best_res = next((r for r in calibration_results if r["threshold"] == best_threshold), {})
    db.execute("""INSERT INTO calibration_runs (ts, phrases_tested, true_positives, false_positives,
                  true_negatives, false_negatives, accuracy, recommended_threshold) VALUES (?,?,?,?,?,?,?,?)""",
               (datetime.now().isoformat(), len(SIMILAR_PHRASES),
                best_res.get("tp", 0), best_res.get("fp", 0),
                best_res.get("tn", 0), best_res.get("fn", 0),
                best_res.get("accuracy", 0), best_threshold))
    db.commit()

    result = {
        "action": "calibrate",
        "phrases_tested": len(SIMILAR_PHRASES),
        "thresholds_tested": len(thresholds_to_test),
        "recommended_threshold": best_threshold,
        "best_f1_score": round(best_accuracy, 3),
        "calibration_grid": calibration_results,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    threshold, preset = get_current_threshold(db)
    tests = db.execute("SELECT COUNT(*) FROM wake_tests").fetchone()[0]
    calibrations = db.execute("SELECT COUNT(*) FROM calibration_runs").fetchone()[0]
    result = {
        "status": "ok",
        "current_threshold": threshold,
        "current_preset": preset,
        "total_tests": tests,
        "total_calibrations": calibrations,
        "presets": {k: v["threshold"] for k, v in SENSITIVITY_PRESETS.items()},
        "similar_phrases_count": len(SIMILAR_PHRASES),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Wake Word Tuner — COWORK #231")
    parser.add_argument("--test", action="store_true", help="Test wake word detection")
    parser.add_argument("--sensitivity", type=float, metavar="N", help="Set sensitivity threshold (0.1-1.0)")
    parser.add_argument("--false-positives", action="store_true", help="Show false positive history")
    parser.add_argument("--calibrate", action="store_true", help="Auto-calibrate threshold")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.test:
        print(json.dumps(do_test(), ensure_ascii=False, indent=2))
    elif args.sensitivity is not None:
        print(json.dumps(do_sensitivity(args.sensitivity), ensure_ascii=False, indent=2))
    elif args.false_positives:
        print(json.dumps(do_false_positives(), ensure_ascii=False, indent=2))
    elif args.calibrate:
        print(json.dumps(do_calibrate(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
