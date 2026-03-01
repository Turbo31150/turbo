"""JARVIS Command Executor — Executes matched voice commands on the system."""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

from src.commands import (
    JarvisCommand, APP_PATHS, SITE_ALIASES,
    match_command, correct_voice_text, format_commands_help,
)
from src.windows import run_powershell, open_application
from src.config import SCRIPTS
from src.signal_formatter import parse_sniper_json, format_telegram_signals, format_chat_signals


async def execute_command(cmd: JarvisCommand, params: dict[str, str]) -> str:
    """Execute a matched command and return the result text."""

    if cmd.action_type == "exit":
        return "__EXIT__"

    if cmd.action_type == "list_commands":
        return format_commands_help()

    if cmd.action_type == "jarvis_repeat":
        return "__REPEAT__"

    if cmd.action_type == "app_open":
        app_name = cmd.action
        if "{" in app_name and params:
            for k, v in params.items():
                app_name = app_name.replace(f"{{{k}}}", v)
        resolved = APP_PATHS.get(app_name.lower(), app_name)
        result = run_powershell(f"Start-Process '{resolved}'", timeout=10)
        if result["success"]:
            return f"Application {app_name} ouverte."
        else:
            return f"Impossible d'ouvrir {app_name}: {result['stderr']}"

    if cmd.action_type == "ms_settings":
        uri = cmd.action
        result = run_powershell(f"Start-Process '{uri}'", timeout=10)
        if result["success"]:
            return f"Parametres ouverts: {uri}"
        else:
            return f"Erreur ouverture parametres: {result['stderr']}"

    if cmd.action_type == "hotkey":
        action = cmd.action
        for k, v in params.items():
            action = action.replace(f"{{{k}}}", v)
        return _execute_hotkey(action)

    if cmd.action_type == "browser":
        action = cmd.action
        for k, v in params.items():
            action = action.replace(f"{{{k}}}", v)

        if action.startswith("navigate:"):
            url = action[len("navigate:"):]
            url = SITE_ALIASES.get(url.lower(), url)
            if not url.startswith("http"):
                url = f"https://{url}"
            result = run_powershell(f"Start-Process chrome '{url}'", timeout=10)
            if result["success"]:
                return f"Navigation vers {url}."
            else:
                return f"Erreur navigation: {result['stderr']}"

        elif action.startswith("search:"):
            query = action[len("search:"):]
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            result = run_powershell(f"Start-Process chrome '{url}'", timeout=10)
            if result["success"]:
                return f"Recherche Google: {query}."
            else:
                return f"Erreur recherche: {result['stderr']}"

    if cmd.action_type == "powershell":
        action = cmd.action
        for k, v in params.items():
            action = action.replace(f"{{{k}}}", v)
        result = run_powershell(action, timeout=30)
        if result["success"]:
            output = result["stdout"][:200] if result["stdout"] else "OK"
            return f"Commande executee. {output}"
        else:
            return f"Erreur: {result['stderr'][:200]}"

    if cmd.action_type == "script":
        import sys
        import shlex
        parts = shlex.split(cmd.action)
        script_name = parts[0]
        script_args = parts[1:]
        script_path = SCRIPTS.get(script_name)
        if not script_path or not script_path.exists():
            return f"Script introuvable: {script_name}"
        try:
            # Run in thread to avoid blocking the async event loop
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, str(script_path)] + script_args,
                capture_output=True, text=True, timeout=120,
                cwd=str(script_path.parent),
            )
            # Trading scripts: keep full output for JSON parsing + Telegram
            formatted = _postprocess_trading_script(script_name, result.stdout)
            if formatted:
                return formatted
            # Default: truncate for non-trading scripts
            output = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            return f"Script {script_name} termine (exit={result.returncode}). {output}"
        except subprocess.TimeoutExpired:
            return f"Script {script_name} timeout (120s)."
        except Exception as e:
            return f"Erreur script: {e}"

    if cmd.action_type == "jarvis_tool":
        action = cmd.action
        for k, v in params.items():
            action = action.replace(f"{{{k}}}", v)
        return f"__TOOL__{action}"

    if cmd.action_type == "pipeline":
        return await _execute_pipeline(cmd.action, params or {})

    return f"Type d'action inconnu: {cmd.action_type}"


async def _execute_pipeline(action: str, params: dict[str, str]) -> str:
    """Execute a multi-step pipeline. Steps separated by ';;'.

    Each step: 'type:action' where type is powershell, app_open, browser, etc.
    Special: 'sleep:N' pauses N seconds between steps.
    """
    steps = [s.strip() for s in action.split(";;") if s.strip()]
    results = []

    for step in steps:
        if step.startswith("sleep:"):
            try:
                await asyncio.sleep(float(step[6:]))
            except ValueError:
                pass
            continue

        sep = step.find(":")
        if sep == -1:
            results.append(f"Step invalide: {step}")
            continue

        step_type = step[:sep].strip()
        step_action = step[sep + 1:].strip()

        if step_type == "pipeline":
            results.append("Erreur: pipeline imbriquee non supportee")
            continue

        for k, v in params.items():
            step_action = step_action.replace(f"{{{k}}}", v)

        sub_cmd = JarvisCommand(
            name="pipeline_step",
            category="pipeline",
            description="",
            triggers=[],
            action_type=step_type,
            action=step_action,
        )
        result = await execute_command(sub_cmd, {})
        if result and not result.startswith("__"):
            results.append(result)

    return " | ".join(results) if results else "Pipeline execute"


# ═══════════════════════════════════════════════════════════════════════════
# TRADING SCRIPT POST-PROCESSING
# ═══════════════════════════════════════════════════════════════════════════

_TRADING_SCRIPTS = {"scan_sniper", "mexc_scanner"}


def _postprocess_trading_script(script_name: str, stdout: str) -> str | None:
    """Parse JSON output from trading scripts, format for chat, send Telegram.

    Returns formatted chat string, or None to fall back to default truncation.
    """
    if script_name not in _TRADING_SCRIPTS:
        return None
    data = parse_sniper_json(stdout)
    if not data or not data.get("signals"):
        return None
    # Send Telegram notification (fire-and-forget, don't block on failure)
    try:
        from src.trading import send_telegram
        import logging
        tg_msg = format_telegram_signals(data)
        ok = send_telegram(tg_msg)
        logging.getLogger("jarvis.executor").info(
            "Telegram sniper: %s (%d signals)", "sent" if ok else "failed", len(data.get("signals", []))
        )
    except Exception as e:
        logging.getLogger("jarvis.executor").warning("Telegram sniper error: %s", e)
    # Return structured chat format
    return format_chat_signals(data)


# ═══════════════════════════════════════════════════════════════════════════
# SKILL / PIPELINE EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

async def execute_skill_step(step, mcp_call) -> str:
    """Execute a single skill step using the MCP callback.

    Args:
        step: SkillStep with tool name and args
        mcp_call: async callable(tool_name, args) -> str
    """
    from src.skills import log_action
    try:
        result = await mcp_call(step.tool, step.args)
        log_action(f"{step.tool}({step.args})", result, True)
        return result
    except Exception as e:
        log_action(f"{step.tool}({step.args})", str(e), False)
        return f"Erreur {step.tool}: {e}"


async def execute_skill(skill, mcp_call) -> str:
    """Execute a full skill pipeline.

    Args:
        skill: Skill object with steps
        mcp_call: async callable(tool_name, args) -> str
    """
    from src.skills import record_skill_use
    results = []
    all_success = True

    for i, step in enumerate(skill.steps):
        desc = step.description or step.tool
        results.append(f"[{i+1}/{len(skill.steps)}] {desc}...")
        result = await execute_skill_step(step, mcp_call)
        if "ERREUR" in result.upper():
            all_success = False
            results.append(f"  Erreur: {result[:100]}")
        else:
            results.append(f"  OK: {result[:150]}")

    record_skill_use(skill.name, all_success)
    status = "termine" if all_success else "termine avec erreurs"
    return f"Skill '{skill.name}' {status}.\n" + "\n".join(results)


# ═══════════════════════════════════════════════════════════════════════════
# HOTKEY EXECUTION
# ═══════════════════════════════════════════════════════════════════════════

def _win_hotkey_ps(letter: str) -> str:
    """PowerShell to simulate Win+Letter via keybd_event."""
    vk = ord(letter.upper())
    return (
        f"Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        f"public class K{{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}}'; "
        f"[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event({vk},0,0,0); "
        f"[K]::keybd_event({vk},0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    )


def _win_arrow_ps(direction: str) -> str:
    """PowerShell to simulate Win+Arrow via keybd_event."""
    vk_map = {"UP": "0x26", "DOWN": "0x28", "LEFT": "0x25", "RIGHT": "0x27"}
    vk = vk_map[direction]
    return (
        f"Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        f"public class K{{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}}'; "
        f"[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event({vk},0,0,0); "
        f"[K]::keybd_event({vk},0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    )


def _win_tab_ps() -> str:
    """PowerShell to simulate Win+Tab (Task View)."""
    return (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x09,0,0,0); "
        "[K]::keybd_event(0x09,0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    )


def _ctrl_win_arrow_ps(direction: str) -> str:
    """PowerShell to simulate Ctrl+Win+Arrow for virtual desktop switching."""
    vk_map = {"LEFT": "0x25", "RIGHT": "0x27"}
    vk = vk_map[direction]
    return (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        f"[K]::keybd_event(0x11,0,0,0); [K]::keybd_event(0x5B,0,0,0); "
        f"[K]::keybd_event({vk},0,0,0); [K]::keybd_event({vk},0,2,0); "
        "[K]::keybd_event(0x5B,0,2,0); [K]::keybd_event(0x11,0,2,0)"
    )


def _win_semicolon_ps() -> str:
    """PowerShell to simulate Win+; (emoji panel, VK_OEM_1 = 0xBA)."""
    return (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0xBA,0,0,0); "
        "[K]::keybd_event(0xBA,0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    )


def _win_shift_s_ps() -> str:
    """PowerShell to simulate Win+Shift+S (screenshot)."""
    return (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x10,0,0,0); [K]::keybd_event(0x53,0,0,0); "
        "[K]::keybd_event(0x53,0,2,0); [K]::keybd_event(0x10,0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    )


# Map of hotkey names to PowerShell WScript.Shell SendKeys or VK codes
HOTKEY_MAP: dict[str, str] = {
    # Media keys (virtual key codes)
    "media_play_pause": "(New-Object -ComObject WScript.Shell).SendKeys([char]179)",
    "media_next": "(New-Object -ComObject WScript.Shell).SendKeys([char]176)",
    "media_previous": "(New-Object -ComObject WScript.Shell).SendKeys([char]177)",
    "media_stop": "(New-Object -ComObject WScript.Shell).SendKeys([char]178)",
    "volume_up": "(New-Object -ComObject WScript.Shell).SendKeys([char]175)",
    "volume_down": "(New-Object -ComObject WScript.Shell).SendKeys([char]174)",
    "volume_mute": "(New-Object -ComObject WScript.Shell).SendKeys([char]173)",
    # Keyboard shortcuts (SendKeys syntax)
    "ctrl+c": "(New-Object -ComObject WScript.Shell).SendKeys('^c')",
    "ctrl+v": "(New-Object -ComObject WScript.Shell).SendKeys('^v')",
    "ctrl+x": "(New-Object -ComObject WScript.Shell).SendKeys('^x')",
    "ctrl+z": "(New-Object -ComObject WScript.Shell).SendKeys('^z')",
    "ctrl+y": "(New-Object -ComObject WScript.Shell).SendKeys('^y')",
    "ctrl+a": "(New-Object -ComObject WScript.Shell).SendKeys('^a')",
    "ctrl+s": "(New-Object -ComObject WScript.Shell).SendKeys('^s')",
    "ctrl+t": "(New-Object -ComObject WScript.Shell).SendKeys('^t')",
    "ctrl+w": "(New-Object -ComObject WScript.Shell).SendKeys('^w')",
    "ctrl+f": "(New-Object -ComObject WScript.Shell).SendKeys('^f')",
    "alt+tab": "(New-Object -ComObject WScript.Shell).SendKeys('%{TAB}')",
    "alt+F4": "(New-Object -ComObject WScript.Shell).SendKeys('%{F4}')",
    # Win key combos (use PowerShell keybd_event)
    "win+d": _win_hotkey_ps("D"),
    "win+e": _win_hotkey_ps("E"),
    "win+l": _win_hotkey_ps("L"),
    "win+r": _win_hotkey_ps("R"),
    "win+a": _win_hotkey_ps("A"),
    "win+up": _win_arrow_ps("UP"),
    "win+down": _win_arrow_ps("DOWN"),
    "win+left": _win_arrow_ps("LEFT"),
    "win+right": _win_arrow_ps("RIGHT"),
    "win+shift+s": _win_shift_s_ps(),
    # Win key combos supplementaires (Windows 11)
    "win+s": _win_hotkey_ps("S"),         # Recherche Windows
    "win+n": _win_hotkey_ps("N"),         # Centre notifications
    "win+w": _win_hotkey_ps("W"),         # Widgets
    "win+v": _win_hotkey_ps("V"),         # Historique presse-papier
    "win+p": _win_hotkey_ps("P"),         # Projeter ecran
    "win+tab": _win_tab_ps(),             # Vue des taches
    "win+;": _win_semicolon_ps(),         # Panneau emojis
    # Bureaux virtuels
    "ctrl+win+right": _ctrl_win_arrow_ps("RIGHT"),
    "ctrl+win+left": _ctrl_win_arrow_ps("LEFT"),
    # Bureaux virtuels avances
    "ctrl+win+d": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x11,0,0,0); [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x44,0,0,0); "
        "[K]::keybd_event(0x44,0,2,0); [K]::keybd_event(0x5B,0,2,0); [K]::keybd_event(0x11,0,2,0)"
    ),
    "ctrl+win+F4": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x11,0,0,0); [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x73,0,0,0); "
        "[K]::keybd_event(0x73,0,2,0); [K]::keybd_event(0x5B,0,2,0); [K]::keybd_event(0x11,0,2,0)"
    ),
    # Navigation/Edition
    "ctrl++": "(New-Object -ComObject WScript.Shell).SendKeys('^{+}')",
    "ctrl+-": "(New-Object -ComObject WScript.Shell).SendKeys('^{-}')",
    "ctrl+0": "(New-Object -ComObject WScript.Shell).SendKeys('^0')",
    "ctrl+p": "(New-Object -ComObject WScript.Shell).SendKeys('^p')",
    "F2": "(New-Object -ComObject WScript.Shell).SendKeys('{F2}')",
    "F5": "(New-Object -ComObject WScript.Shell).SendKeys('{F5}')",
    "delete": "(New-Object -ComObject WScript.Shell).SendKeys('{DELETE}')",
    "alt+enter": "(New-Object -ComObject WScript.Shell).SendKeys('%{ENTER}')",
    # Vague 3 — Accessibilite
    "win++": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0xBB,0,0,0); "
        "[K]::keybd_event(0xBB,0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    ),
    "win+escape": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x1B,0,0,0); "
        "[K]::keybd_event(0x1B,0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    ),
    "ctrl+win+enter": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x11,0,0,0); [K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x0D,0,0,0); "
        "[K]::keybd_event(0x0D,0,2,0); [K]::keybd_event(0x5B,0,2,0); [K]::keybd_event(0x11,0,2,0)"
    ),
    "win+h": _win_hotkey_ps("H"),           # Dictee vocale
    "alt+shift+print": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x12,0,0,0); [K]::keybd_event(0x10,0,0,0); [K]::keybd_event(0x2C,0,0,0); "
        "[K]::keybd_event(0x2C,0,2,0); [K]::keybd_event(0x10,0,2,0); [K]::keybd_event(0x12,0,2,0)"
    ),
    # Vague 3 — Multimedia / Game Bar
    "win+alt+r": (
        "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
        "public class K{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte k,byte s,int f,int e);}'; "
        "[K]::keybd_event(0x5B,0,0,0); [K]::keybd_event(0x12,0,0,0); [K]::keybd_event(0x52,0,0,0); "
        "[K]::keybd_event(0x52,0,2,0); [K]::keybd_event(0x12,0,2,0); [K]::keybd_event(0x5B,0,2,0)"
    ),
    "win+g": _win_hotkey_ps("G"),           # Xbox Game Bar
    "win+z": _win_hotkey_ps("Z"),           # Snap Layout
    # Vague 3 — Chrome navigation
    "ctrl+h": "(New-Object -ComObject WScript.Shell).SendKeys('^h')",
    "ctrl+d": "(New-Object -ComObject WScript.Shell).SendKeys('^d')",
    "ctrl+j": "(New-Object -ComObject WScript.Shell).SendKeys('^j')",
    # Vague 5 — Miracast
    "win+k": _win_hotkey_ps("K"),           # Connect / Miracast
}


def _execute_hotkey(key: str) -> str:
    """Execute a hotkey by name."""
    ps_cmd = HOTKEY_MAP.get(key)
    if not ps_cmd:
        return f"Raccourci inconnu: {key}"
    result = run_powershell(ps_cmd, timeout=5)
    if result["success"]:
        return f"Raccourci {key} execute."
    else:
        return f"Erreur raccourci: {result['stderr'][:100]}"


async def process_voice_input(text: str) -> tuple[str, float]:
    """Process raw voice input: correct, match, execute.

    Returns: (response_text, confidence_score)
    """
    # Step 1: Correct voice errors
    corrected = correct_voice_text(text)

    # Step 2: Try to match a pre-registered command
    cmd, params, score = match_command(corrected)

    if cmd is None:
        # No match — return corrected text for JARVIS to handle via IA
        return f"__FREEFORM__{corrected}", score

    # Step 3: Check if confirmation needed
    if cmd.confirm:
        return f"__CONFIRM__{cmd.name}|{cmd.description}", score

    # Step 4: Execute the command
    result = await execute_command(cmd, params)
    return result, score


async def correct_with_ia(text: str, node_url: str = "http://127.0.0.1:11434") -> str:
    """Use Ollama qwen3:1.7b (primary) or M1 fallback to correct voice transcription."""
    import httpx
    from src.config import config
    prompt = (
        "Tu es un correcteur de texte francais specialise dans la correction "
        "de transcriptions vocales. Corrige les erreurs sans changer le sens. "
        "Reponds UNIQUEMENT avec le texte corrige, rien d'autre.\n\n"
        f"Texte a corriger: {text}"
    )
    messages = [{"role": "user", "content": prompt}]
    # Primary: Ollama qwen3:1.7b (fast, lightweight)
    ol = config.get_ollama_node("OL1")
    if ol:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{ol.url}/api/chat",
                    json={
                        "model": "qwen3:1.7b", "messages": messages,
                        "stream": False, "think": False,
                        "options": {"temperature": 0.1, "num_predict": 256},
                    },
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"].strip()
        except Exception:
            pass
    return correct_voice_text(text)
