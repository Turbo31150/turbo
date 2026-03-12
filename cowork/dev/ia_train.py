#!/usr/bin/env python3
"""IA Training — record feedback examples for intent classifier."""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

TRAINING_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "intent_training.jsonl")

def record_example(text: str, intent: str, correct: bool = True):
    entry = {"text": text, "intent": intent, "correct": correct}
    with open(TRAINING_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry

def show_stats():
    if not os.path.exists(TRAINING_FILE):
        print("No training data yet")
        return
    from collections import Counter
    intents = Counter()
    total = 0
    with open(TRAINING_FILE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                intents[entry["intent"]] += 1
                total += 1
    print(f"Total examples: {total}")
    for intent, count in intents.most_common():
        print(f"  {intent}: {count}")

def main():
    parser = argparse.ArgumentParser(description="Intent classifier training data")
    parser.add_argument("--add", nargs=2, metavar=("TEXT", "INTENT"), help="Add training example")
    parser.add_argument("--stats", action="store_true", help="Show training stats")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.add:
        entry = record_example(args.add[0], args.add[1])
        print(f"Recorded: {entry}")
    elif args.stats:
        show_stats()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
