"""lienDepart — Point d'entree principal."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def main():
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="lienDepart — Hyper-orchestrateur multi-agents")
    parser.add_argument("prompt", nargs="*", help="Prompt en mode one-shot")
    parser.add_argument("--interactive", "-i", action="store_true", help="Mode interactif REPL")
    parser.add_argument("--cwd", default="F:/BUREAU/lienDepart", help="Working directory")
    args = parser.parse_args()

    from src.orchestrator import run_once, run_interactive

    if args.interactive or not args.prompt:
        asyncio.run(run_interactive(cwd=args.cwd))
    else:
        prompt = " ".join(args.prompt)
        result = asyncio.run(run_once(prompt, cwd=args.cwd))
        if result:
            print(result)


if __name__ == "__main__":
    main()
