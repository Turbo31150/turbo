"""Task Watcher - Pont Claude Code <-> Perplexity pour JARVIS."""
import time
import json
from pathlib import Path
from datetime import datetime

INBOX = Path("/home/turbo/jarvis-m1-ops/tasks/for_perplexity")
OUTBOX = Path("/home/turbo/jarvis-m1-ops/tasks/from_perplexity")
ARCHIVE = Path("/home/turbo/jarvis-m1-ops/tasks/archive")

def watch_tasks():
    """Surveille les nouvelles taches de Claude Code."""
    print("Watching for Claude Code tasks...")
    seen = set()

    while True:
        for task_file in sorted(INBOX.glob("task_*.md")):
            if task_file.name in seen:
                continue
            content = task_file.read_text(encoding="utf-8")
            if "=== READY FOR PERPLEXITY ===" not in content:
                continue
            seen.add(task_file.name)
            print(f"\n[NEW TASK] {task_file.name}")
            print(f"  Copie le contenu dans Perplexity, puis colle la reponse dans:")
            print(f"  {OUTBOX / task_file.name.replace('task_', 'result_')}")

            # Attend validation manuelle
            result_file = OUTBOX / task_file.name.replace("task_", "result_")
            while not result_file.exists():
                time.sleep(10)

            print(f"  [DONE] Resultat recu: {result_file.name}")
            task_file.rename(ARCHIVE / f"{datetime.now().strftime('%Y%m%d_%H%M')}_{task_file.name}")

        time.sleep(15)

if __name__ == "__main__":
    watch_tasks()
