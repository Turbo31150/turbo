
import os
import re
from pathlib import Path

def generate_env_example():
    env_path = Path("/home/turbo/jarvis/.env")
    example_path = Path("/home/turbo/jarvis/.env.example")
    
    if not env_path.exists():
        print("No .env found.")
        return

    with open(env_path, 'r') as f:
        lines = f.readlines()

    example_lines = []
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key = line.split("=")[0]
            example_lines.append(f"{key}=REDACTED\n")
        else:
            example_lines.append(line)

    with open(example_path, 'w') as f:
        f.writelines(example_lines)
    
    print("✅ .env.example updated (all keys redacted).")

if __name__ == "__main__":
    generate_env_example()
