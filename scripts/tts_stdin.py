"""TTS wrapper that reads text from stdin — avoids shell escaping issues.

Usage: echo "Bonjour" | python scripts/tts_stdin.py [--telegram]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, "C:/Users/franc/.openclaw/workspace/dev")

from win_tts import speak_and_send

text = sys.stdin.read().strip()
if not text:
    print(json.dumps({"ok": False, "error": "empty text"}))
    sys.exit(1)

telegram = "--telegram" in sys.argv
result = speak_and_send(text, telegram=telegram)
print(json.dumps(result, ensure_ascii=False))
