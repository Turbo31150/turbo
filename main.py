"""JARVIS Turbo - Entry point."""

from __future__ import annotations

import asyncio
import io
import os
import sys

# Force UTF-8 output on Windows to avoid cp1252 emoji crashes
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from src.orchestrator import run_once, run_interactive, run_voice, run_hybrid, run_commander
from src.cluster_startup import ensure_cluster_ready, print_startup_report


async def _run_ollama_mode() -> None:
    """Launch Claude Code powered by Ollama cloud model (free, web search + sub-agents).

    Uses 'ollama launch claude --model <model>' which provides:
    - Sub-agents: parallel tasks (file search, code exploration, web research)
    - Web search: built-in, no MCP/API key needed
    - Recommended models: minimax-m2.5:cloud, glm-5:cloud, kimi-k2.5:cloud
    """
    import subprocess
    args = sys.argv[2:]  # Extra args after --ollama
    model = "minimax-m2.5:cloud"
    # Allow model override: --ollama glm-5:cloud
    if args and not args[0].startswith("-"):
        model = args[0]
        args = args[1:]
    print(f"=== JARVIS OLLAMA MODE — {model} ===")
    print("Claude Code alimente par Ollama cloud (gratuit)")
    print("Sous-agents + recherche web natifs")
    print("=" * 50)
    cmd = ["ollama", "launch", "claude", "--model", model]
    if args:
        cmd.append("--")
        cmd.extend(args)
    try:
        subprocess.run(cmd, cwd="F:/BUREAU/turbo")
    except FileNotFoundError:
        print("[ERREUR] 'ollama' non trouve dans le PATH. Installe-le depuis https://ollama.com")
    except KeyboardInterrupt:
        print("\n[JARVIS] Session Ollama terminee.")


async def main() -> None:
    args = sys.argv[1:]

    # Auto-startup: ensure cluster models are loaded (skip for --help, --ollama, and quick queries)
    if not args or args[0] not in ("-h", "--help", "-o", "--ollama"):
        report = await ensure_cluster_ready()
        print_startup_report(report)

    if not args or args[0] in ("-i", "--interactive"):
        await run_interactive()
    elif args[0] in ("-c", "--commander"):
        await run_commander()
    elif args[0] in ("-v", "--voice", "--vocal"):
        await run_voice()
    elif args[0] in ("-k", "--keyboard", "--hybrid"):
        await run_hybrid()
    elif args[0] in ("-o", "--ollama"):
        await _run_ollama_mode()
    elif args[0] in ("-s", "--status"):
        await run_once("Utilise lm_cluster_status et rapporte le statut du cluster.")
    elif args[0] in ("-h", "--help"):
        print(
            "JARVIS Turbo — Orchestrateur IA Distribue\n"
            "\n"
            "Usage:\n"
            "  python main.py                   Mode interactif (REPL)\n"
            "  python main.py -i                Mode interactif (REPL)\n"
            "  python main.py -c                Mode Commandant (Claude = orchestrateur pur)\n"
            "  python main.py -v                Mode vocal (PTT CTRL)\n"
            "  python main.py -k                Mode clavier (hybride)\n"
            "  python main.py -o                Mode Ollama cloud (gratuit, web + sub-agents)\n"
            "  python main.py -o glm-5:cloud    Ollama avec modele specifique\n"
            "  python main.py -s                Statut du cluster\n"
            '  python main.py "<prompt>"        Requete unique (IAs)\n'
            "  python main.py -h                Aide"
        )
    else:
        prompt = " ".join(args)
        await run_once(prompt)


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
