
import os
import re
from pathlib import Path

ROOT = "/home/turbo/jarvis"
OLD_WIN_PATH = r"F:/BUREAU/turbo"
OLD_WIN_PATH_ESC = r"F:\\BUREAU\\turbo"

REPLACEMENTS = [
    (OLD_WIN_PATH, ROOT),
    (OLD_WIN_PATH_ESC, ROOT),
    (r"C:\\Users\\franc", "/home/turbo"),
    (r".exe", ""),
    (r"powershell", "bash"),
    (r"Start-Process", "xdg-open"),
    (r"Invoke-WebRequest", "curl"),
]

def refactor_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        new_content = content
        for old, new in REPLACEMENTS:
            new_content = re.sub(re.escape(old), new, new_content, flags=re.IGNORECASE)
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
    except Exception as e:
        print(f"Error in {file_path}: {e}")
    return False

def run_migration():
    print(f"🚀 Starting Global Refactor in {ROOT}...")
    count = 0
    for root, dirs, files in os.walk(ROOT):
        if any(x in root for x in [".git", ".venv", "node_modules"]):
            continue
        for file in files:
            if file.endswith(('.py', '.sh', '.json', '.md', '.service')):
                if refactor_file(os.path.join(root, file)):
                    count += 1
    print(f"✅ Migration complete. {count} files refactored.")

if __name__ == "__main__":
    run_migration()
