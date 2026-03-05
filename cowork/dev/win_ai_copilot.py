#!/usr/bin/env python3
"""win_ai_copilot.py — IA contextual assistant (#243).

Reads clipboard, analyzes current window title, suggests actions based on context.
Uses ctypes for clipboard (CF_UNICODETEXT=13) and foreground window.

Usage:
    python dev/win_ai_copilot.py --once
    python dev/win_ai_copilot.py --analyze
    python dev/win_ai_copilot.py --suggest
    python dev/win_ai_copilot.py --clipboard
    python dev/win_ai_copilot.py --context
"""
import argparse
import ctypes
import ctypes.wintypes
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "ai_copilot.db"

# Constants
CF_UNICODETEXT = 13


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        window_title TEXT,
        clipboard_text TEXT,
        detected_context TEXT,
        suggestions TEXT,
        action_taken TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        context_type TEXT,
        suggestion TEXT,
        confidence REAL,
        applied INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def get_clipboard_text():
    """Read clipboard text using ctypes (CF_UNICODETEXT=13)."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    text = ""
    try:
        if user32.OpenClipboard(0):
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                kernel32.GlobalLock.restype = ctypes.c_wchar_p
                raw = kernel32.GlobalLock(handle)
                if raw:
                    text = str(raw)
                kernel32.GlobalUnlock(handle)
            user32.CloseClipboard()
    except Exception as e:
        text = f"[error: {e}]"
    return text


def get_foreground_window_title():
    """Get the title of the currently focused window."""
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def detect_context(window_title, clipboard_text):
    """Detect context from window title and clipboard content."""
    title_lower = window_title.lower() if window_title else ""
    contexts = []

    # IDE / Code editor detection
    if any(k in title_lower for k in ["visual studio", "vscode", "code -", ".py", ".js", ".ts", "lm studio"]):
        contexts.append("coding")
    # Browser
    if any(k in title_lower for k in ["chrome", "firefox", "edge", "brave", "opera"]):
        contexts.append("browsing")
    # Terminal
    if any(k in title_lower for k in ["cmd", "powershell", "terminal", "bash", "wsl", "windows terminal"]):
        contexts.append("terminal")
    # File manager
    if any(k in title_lower for k in ["explorer", "dossier", "fichier"]):
        contexts.append("file_management")
    # Communication
    if any(k in title_lower for k in ["telegram", "discord", "slack", "teams", "outlook", "mail"]):
        contexts.append("communication")
    # Trading
    if any(k in title_lower for k in ["mexc", "binance", "trading", "crypto"]):
        contexts.append("trading")
    # Document
    if any(k in title_lower for k in ["word", "notepad", "notion", "obsidian", ".md", ".txt"]):
        contexts.append("documentation")

    # Clipboard content analysis
    if clipboard_text:
        clip_lower = clipboard_text.lower()
        if any(k in clip_lower for k in ["def ", "class ", "import ", "function", "const ", "var "]):
            if "coding" not in contexts:
                contexts.append("coding")
        if any(k in clip_lower for k in ["http://", "https://", "www."]):
            contexts.append("url_detected")
        if any(k in clip_lower for k in ["error", "traceback", "exception", "failed"]):
            contexts.append("error_detected")
        if "@" in clip_lower and "." in clip_lower:
            contexts.append("email_detected")

    return contexts if contexts else ["general"]


def generate_suggestions(contexts, window_title, clipboard_text):
    """Generate action suggestions based on detected context."""
    suggestions = []

    for ctx in contexts:
        if ctx == "coding":
            suggestions.append({"action": "code_review", "label": "Lancer une revue de code via MAO consensus", "confidence": 0.85})
            suggestions.append({"action": "run_tests", "label": "Executer les tests du fichier courant", "confidence": 0.7})
        elif ctx == "error_detected":
            suggestions.append({"action": "debug_error", "label": "Analyser l'erreur via M1+gpt-oss", "confidence": 0.95})
            suggestions.append({"action": "search_fix", "label": "Rechercher un fix connu", "confidence": 0.8})
        elif ctx == "browsing":
            suggestions.append({"action": "save_page", "label": "Sauvegarder le contenu de la page", "confidence": 0.6})
            suggestions.append({"action": "web_search", "label": "Recherche web via minimax", "confidence": 0.7})
        elif ctx == "terminal":
            suggestions.append({"action": "command_help", "label": "Aide sur la derniere commande", "confidence": 0.75})
            suggestions.append({"action": "script_gen", "label": "Generer un script depuis la commande", "confidence": 0.65})
        elif ctx == "communication":
            suggestions.append({"action": "draft_reply", "label": "Generer un brouillon de reponse", "confidence": 0.7})
        elif ctx == "trading":
            suggestions.append({"action": "market_scan", "label": "Scanner les marches via pipeline trading", "confidence": 0.85})
        elif ctx == "url_detected":
            suggestions.append({"action": "fetch_url", "label": "Fetcher et analyser l'URL du clipboard", "confidence": 0.8})
        elif ctx == "file_management":
            suggestions.append({"action": "organize_files", "label": "Organiser les fichiers du dossier", "confidence": 0.6})
        elif ctx == "documentation":
            suggestions.append({"action": "improve_doc", "label": "Ameliorer la documentation", "confidence": 0.7})
        elif ctx == "general":
            suggestions.append({"action": "quick_ask", "label": "Poser une question rapide a OL1", "confidence": 0.5})

    # Sort by confidence
    suggestions.sort(key=lambda s: s["confidence"], reverse=True)
    return suggestions[:5]


def do_clipboard():
    """Read and analyze clipboard content."""
    db = init_db()
    text = get_clipboard_text()
    result = {
        "ts": datetime.now().isoformat(),
        "clipboard_text": text[:500] if text else None,
        "clipboard_length": len(text) if text else 0,
        "has_content": bool(text and text.strip()),
    }
    if text:
        # Quick classification
        clip_lower = text.lower()
        result["detected_types"] = []
        if any(k in clip_lower for k in ["def ", "class ", "import "]):
            result["detected_types"].append("python_code")
        if any(k in clip_lower for k in ["http://", "https://"]):
            result["detected_types"].append("url")
        if "error" in clip_lower or "traceback" in clip_lower:
            result["detected_types"].append("error_log")
        if any(k in clip_lower for k in ["{", "}", "[", "]"]) and (":" in clip_lower or "," in clip_lower):
            result["detected_types"].append("structured_data")
        if not result["detected_types"]:
            result["detected_types"].append("plain_text")
    db.close()
    return result


def do_context():
    """Get current window context."""
    db = init_db()
    window_title = get_foreground_window_title()
    clipboard_text = get_clipboard_text()
    contexts = detect_context(window_title, clipboard_text)

    result = {
        "ts": datetime.now().isoformat(),
        "window_title": window_title,
        "clipboard_preview": (clipboard_text[:200] + "...") if clipboard_text and len(clipboard_text) > 200 else clipboard_text,
        "detected_contexts": contexts,
    }

    db.execute(
        "INSERT INTO contexts (ts, window_title, clipboard_text, detected_context) VALUES (?,?,?,?)",
        (result["ts"], window_title, clipboard_text[:1000] if clipboard_text else None, json.dumps(contexts)),
    )
    db.commit()
    db.close()
    return result


def do_analyze():
    """Full contextual analysis."""
    db = init_db()
    window_title = get_foreground_window_title()
    clipboard_text = get_clipboard_text()
    contexts = detect_context(window_title, clipboard_text)
    suggestions = generate_suggestions(contexts, window_title, clipboard_text)

    result = {
        "ts": datetime.now().isoformat(),
        "window_title": window_title,
        "clipboard_preview": (clipboard_text[:200] + "...") if clipboard_text and len(clipboard_text) > 200 else clipboard_text,
        "detected_contexts": contexts,
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
    }

    db.execute(
        "INSERT INTO contexts (ts, window_title, clipboard_text, detected_context, suggestions) VALUES (?,?,?,?,?)",
        (result["ts"], window_title, clipboard_text[:1000] if clipboard_text else None,
         json.dumps(contexts), json.dumps(suggestions)),
    )
    for s in suggestions:
        db.execute(
            "INSERT INTO suggestions (ts, context_type, suggestion, confidence) VALUES (?,?,?,?)",
            (result["ts"], ",".join(contexts), s["label"], s["confidence"]),
        )
    db.commit()
    db.close()
    return result


def do_suggest():
    """Generate suggestions based on current context."""
    db = init_db()
    window_title = get_foreground_window_title()
    clipboard_text = get_clipboard_text()
    contexts = detect_context(window_title, clipboard_text)
    suggestions = generate_suggestions(contexts, window_title, clipboard_text)

    result = {
        "ts": datetime.now().isoformat(),
        "contexts": contexts,
        "suggestions": suggestions,
    }

    for s in suggestions:
        db.execute(
            "INSERT INTO suggestions (ts, context_type, suggestion, confidence) VALUES (?,?,?,?)",
            (result["ts"], ",".join(contexts), s["label"], s["confidence"]),
        )
    db.commit()
    db.close()
    return result


def do_status():
    """Overall copilot status."""
    db = init_db()
    total_contexts = db.execute("SELECT COUNT(*) FROM contexts").fetchone()[0]
    total_suggestions = db.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
    recent = db.execute("SELECT ts, detected_context FROM contexts ORDER BY id DESC LIMIT 5").fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "script": "win_ai_copilot.py",
        "script_id": 243,
        "db": str(DB_PATH),
        "total_contexts_recorded": total_contexts,
        "total_suggestions_generated": total_suggestions,
        "recent_contexts": [{"ts": r[0], "context": r[1]} for r in recent],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="win_ai_copilot.py — IA contextual assistant (#243)")
    parser.add_argument("--analyze", action="store_true", help="Full contextual analysis")
    parser.add_argument("--suggest", action="store_true", help="Generate suggestions for current context")
    parser.add_argument("--clipboard", action="store_true", help="Read and analyze clipboard content")
    parser.add_argument("--context", action="store_true", help="Get current window context")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.clipboard:
        result = do_clipboard()
    elif args.analyze:
        result = do_analyze()
    elif args.suggest:
        result = do_suggest()
    elif args.context:
        result = do_context()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
