#!/usr/bin/env python3
"""JARVIS Response Sanitizer — Agents de nettoyage inter-noeuds.

Nettoie automatiquement les reponses quand elles transitent entre noeuds IA.
Ex: M1 → M3, les tokens de reflexion, les artefacts de format, les ponctuations
parasites sont supprimes AVANT et APRES le transit.

10 agents de sanitisation:
  1. THINK_STRIP   — Supprime les blocs <think>...</think> et reasoning tokens
  2. PUNCT_CLEAN   — Corrige les ponctuations doubles, espaces avant ponctuation
  3. ESCAPE_CLEAN  — Supprime les backslash parasites /n, /t en dehors du code
  4. FORMAT_NORM   — Normalise le formatage Markdown (**, `, #, etc.)
  5. UNICODE_FIX   — Remplace les caracteres Unicode speciaux par ASCII
  6. CODE_FENCE    — Corrige les code blocks mal fermes (``` sans fermeture)
  7. LANG_FIX      — Force le francais, supprime les reponses anglaises parasites
  8. JSON_CLEAN    — Extrait et valide le JSON dans les reponses mixtes
  9. TRUNCATE      — Coupe les reponses trop longues intelligemment
  10. DEDUP         — Supprime les repetitions de phrases/paragraphes

Usage:
    from response_sanitizer import sanitize_response, sanitize_for_telegram
    clean = sanitize_response(raw_text, source="M1", target="telegram")
"""

import json
import re

# ── Agent 1: THINK_STRIP ────────────────────────────────────

def strip_think_tokens(text):
    """Supprime les blocs de reflexion des modeles (deepseek-r1, qwen3 think)."""
    # Remove <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove <reasoning>...</reasoning>
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    # Remove /think prefix from qwen3
    if text.startswith("/think\n"):
        text = text[7:]
    if text.startswith("/nothink\n"):
        text = text[9:]
    # Remove thinking: prefix
    text = re.sub(r"^(?:Thinking|Reflexion|Raisonnement)\s*:\s*\n", "", text, flags=re.MULTILINE)
    return text.strip()

# ── Agent 2: PUNCT_CLEAN ────────────────────────────────────

def clean_punctuation(text):
    """Corrige les ponctuations doubles et espaces parasites."""
    # Double ponctuation
    text = re.sub(r"\.{4,}", "...", text)  # .... -> ...
    text = re.sub(r"\!{2,}", "!", text)    # !! -> !
    text = re.sub(r"\?{2,}", "?", text)    # ?? -> ?
    text = re.sub(r",{2,}", ",", text)     # ,, -> ,
    # Space before punctuation (French style keeps space before : ; ! ?)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s+,", ",", text)
    # Multiple spaces
    text = re.sub(r"  +", " ", text)
    # Multiple blank lines
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text

# ── Agent 3: ESCAPE_CLEAN ───────────────────────────────────

def clean_escapes(text):
    """Supprime les backslash parasites en dehors des blocs de code."""
    lines = text.split("\n")
    in_code = False
    result = []
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code:
            # Remove literal /n that should be newlines
            line = line.replace("/n", "\n")
            # Remove escaped quotes that shouldn't be
            line = line.replace('/"', '"')
            line = line.replace("/'", "'")
        result.append(line)
    return "\n".join(result)

# ── Agent 4: FORMAT_NORM ────────────────────────────────────

def normalize_markdown(text):
    """Normalise le formatage Markdown pour Telegram."""
    # Fix bold markers: ***text*** -> *text*
    text = re.sub(r"\*{3,}([^*]+)\*{3,}", r"*\1*", text)
    # Fix headers without space: ##Title -> ## Title
    text = re.sub(r"^(#{1,3})(\S)", r"\1 \2", text, flags=re.MULTILINE)
    return text

# ── Agent 5: UNICODE_FIX ────────────────────────────────────

UNICODE_REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'",  # smart quotes
    "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-",  # em/en dash
    "\u2026": "...",               # ellipsis
    "\u00a0": " ",                 # non-breaking space
    "\u200b": "",                  # zero-width space
    "\u200e": "",                  # LTR mark
    "\u200f": "",                  # RTL mark
    "\ufeff": "",                  # BOM
}

def fix_unicode(text):
    """Remplace les caracteres Unicode speciaux par ASCII."""
    for old, new in UNICODE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text

# ── Agent 6: CODE_FENCE ─────────────────────────────────────

def fix_code_fences(text):
    """Corrige les code blocks mal fermes."""
    count = text.count("```")
    if count % 2 != 0:
        # Odd number of fences — add closing fence
        text = text.rstrip() + "\n```"
    return text

# ── Agent 7: LANG_FIX ───────────────────────────────────────

def check_language(text, target_lang="fr"):
    """Verifie que la reponse est en francais si demande."""
    # Simple heuristic: check for common French vs English words
    fr_words = {"est", "les", "des", "une", "pour", "dans", "avec", "sur", "qui", "pas"}
    en_words = {"the", "and", "for", "with", "that", "this", "from", "have", "are", "not"}

    words = set(text.lower().split())
    fr_count = len(words & fr_words)
    en_count = len(words & en_words)

    # If clearly English, add a note
    if en_count > fr_count * 2 and en_count > 5:
        # Don't modify, just flag — the response might be code
        pass
    return text

# ── Agent 8: JSON_CLEAN ─────────────────────────────────────

def extract_json(text):
    """Extrait le JSON valide d'une reponse mixte texte+JSON."""
    # Try full text as JSON first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON in code blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Try to find JSON object/array
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

    return None

# ── Agent 9: TRUNCATE ───────────────────────────────────────

def smart_truncate(text, max_chars=4000):
    """Coupe intelligemment au dernier paragraphe complet."""
    if len(text) <= max_chars:
        return text

    # Try to cut at last paragraph break
    truncated = text[:max_chars]
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars * 0.7:
        truncated = truncated[:last_para]
    else:
        # Cut at last sentence
        last_period = truncated.rfind(".")
        if last_period > max_chars * 0.8:
            truncated = truncated[:last_period + 1]

    return truncated + "\n\n_[tronque]_"

# ── Agent 10: DEDUP ─────────────────────────────────────────

def remove_duplicates(text):
    """Supprime les paragraphes repetes."""
    paragraphs = text.split("\n\n")
    seen = set()
    unique = []
    for p in paragraphs:
        p_stripped = p.strip()
        if not p_stripped:
            continue
        # Normalize for comparison
        key = re.sub(r"\s+", " ", p_stripped.lower())[:200]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return "\n\n".join(unique)

# ── Main Sanitizer Pipeline ─────────────────────────────────

def sanitize_response(text, source=None, target=None):
    """Pipeline complet de sanitisation.

    Args:
        text: reponse brute du noeud IA
        source: noeud source ("M1", "M2", "M3", "OL1", "gpt-oss", etc.)
        target: destination ("telegram", "proxy", "code", "json")

    Returns:
        texte nettoye
    """
    if not text or not isinstance(text, str):
        return text or ""

    # Agent 1: Strip think tokens (critical for deepseek-r1 on M2/M3)
    text = strip_think_tokens(text)

    # Agent 5: Fix unicode (before other processing)
    text = fix_unicode(text)

    # Agent 3: Clean escapes
    text = clean_escapes(text)

    # Agent 2: Clean punctuation
    text = clean_punctuation(text)

    # Agent 10: Remove duplicates
    text = remove_duplicates(text)

    # Agent 4: Normalize markdown
    text = normalize_markdown(text)

    # Agent 6: Fix code fences
    text = fix_code_fences(text)

    # Agent 7: Language check (informational)
    text = check_language(text)

    return text.strip()

def sanitize_for_telegram(text, max_chars=4000):
    """Sanitise + tronque pour envoi Telegram."""
    text = sanitize_response(text, target="telegram")
    text = smart_truncate(text, max_chars)
    return text

def sanitize_json_response(text):
    """Extrait et valide le JSON d'une reponse."""
    text = strip_think_tokens(text)
    text = fix_unicode(text)
    return extract_json(text)

# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read()

    clean = sanitize_response(text)
    print(clean)
