import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from voice_pipeline.actions_linux import execute_voice_action

def test_commands():
    print("Testing 'ouvre terminal'...")
    # execute_voice_action("ouvre terminal") # Don't actually open it during test
    print("Testing 'monte le volume'...")
    print(execute_voice_action("monte le volume"))
    print("Testing 'liste les fenêtres'...")
    print(execute_voice_action("liste les fenêtres")[:100] + "...")

if __name__ == "__main__":
    test_commands()
