"""JARVIS Voice Correction — Intelligent correction despite capture errors.

Pipeline: Raw STT → Nettoyage → Corrections locales → Phonetique →
          Fuzzy match → Suggestions → Correction IA → Execution
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher, get_close_matches
from typing import Any

from src.commands import (
    COMMANDS, JarvisCommand, VOICE_CORRECTIONS,
    APP_PATHS, SITE_ALIASES, correct_voice_text,
)


# ═══════════════════════════════════════════════════════════════════════════
# PHONETIC MAP — Sons francais similaires (Whisper confond souvent)
# ═══════════════════════════════════════════════════════════════════════════

# Groupes de sons qui se confondent en francais
PHONETIC_GROUPS: list[list[str]] = [
    ["ai", "e", "est", "et", "es", "ait", "ais"],
    ["au", "o", "eau", "haut", "oh"],
    ["an", "en", "ant", "ent", "amp", "emps"],
    ["on", "ont", "om"],
    ["in", "ain", "ein", "im"],
    ["ou", "oo", "oux"],
    ["eu", "oeu", "eux"],
    ["oi", "oie", "wa"],
    ["ch", "sh"],
    ["g", "j", "ge"],
    ["k", "c", "qu", "q"],
    ["s", "ss", "c", "ce"],
    ["z", "s"],
    ["f", "ph"],
    ["t", "th"],
]

# Mots-outils souvent rajoutes/enleves par le STT
FILLER_WORDS = {
    "euh", "hum", "hmm", "bah", "ben", "bon", "alors",
    "donc", "voila", "ok", "well", "so", "please",
    "s'il te plait", "s'il vous plait", "merci",
    "un peu", "juste", "peut-etre", "genre",
    "tu peux", "est-ce que tu peux", "peux-tu",
    "je veux", "je voudrais", "j'aimerais",
    "est-ce que", "est ce que",
}

# Expansions de commandes implicites
IMPLICIT_COMMANDS: dict[str, str] = {
    "google": "cherche sur google",
    "youtube": "ouvre youtube",
    "gmail": "ouvre gmail",
    "chrome": "ouvre chrome",
    "comet": "ouvre comet",
    "terminal": "ouvre le terminal",
    "vscode": "ouvre vscode",
    "documents": "ouvre mes documents",
    "telechargements": "ouvre les telechargements",
    "bureau": "ouvre le bureau",
    "volume": "monte le volume",
    "mute": "coupe le son",
    "silence": "coupe le son",
    "screenshot": "capture ecran",
    "capture": "capture ecran",
    "scanner": "scanne le marche",
    "breakout": "detecte les breakouts",
    "pipeline": "lance le pipeline",
    "cluster": "statut du cluster",
    "aide": "aide",
    "stop": "stop",
    "status": "statut du cluster",
    # Nouvelles commandes implicites
    "bluetooth": "active le bluetooth",
    "parametres": "ouvre les parametres",
    "reglages": "ouvre les reglages",
    "emojis": "ouvre les emojis",
    "widgets": "ouvre les widgets",
    "notifications": "ouvre les notifications",
    "explorateur": "ouvre l'explorateur de fichiers",
    "wifi": "scan wifi",
    "positions": "mes positions",
    "signaux": "signaux en attente",
    "services": "liste les services",
    "save": "sauvegarde",
    "find": "recherche dans la page",
    "redo": "refais",
    "trading": "statut trading",
    # Vague 2 - Commandes implicites
    "micro": "coupe le micro",
    "camera": "parametres camera",
    "zoom": "zoom avant",
    "print": "imprime",
    "refresh": "actualise",
    "rename": "renomme",
    "delete": "supprime",
    "lock": "verrouille",
    "reunion": "mode reunion",
    "visio": "mode reunion",
    "focus": "mode focus",
    "presentation": "mode presentation",
    "musique": "mets de la musique",
    "diagnostic": "diagnostic complet",
    "monitoring": "monitoring complet",
    "optimisation": "optimise le pc",
    "stream": "mode stream",
    "gaming": "mode gaming",
    "dev": "mode dev",
    # Vague 3 - Accessibilite / Multimedia / Reseau
    "loupe": "active la loupe",
    "narrateur": "active le narrateur",
    "dictee": "lance la dictee",
    "contraste": "contraste eleve",
    "accessibilite": "parametres accessibilite",
    "incognito": "mode incognito",
    "historique": "historique chrome",
    "performance": "mode performance",
    "economie": "mode economie",
    "dns": "vide le cache dns",
    "vpn": "parametres vpn",
    "snap": "snap layout",
    "record": "enregistre l'ecran",
    "ipconfig": "montre l'ip",
    "proxy": "parametres proxy",
    "gamebare": "game bar",
    # Vague 4 - Multi-ecran / Focus / Disques / Taskbar
    "alarme": "ouvre les alarmes",
    "minuteur": "ouvre les alarmes",
    "timer": "ouvre les alarmes",
    "chronometre": "ouvre les alarmes",
    "disques": "info disques",
    "batterie": "parametres batterie",
    "heure": "parametres heure",
    "langue": "parametres langue",
    "souris": "parametres souris",
    "clavier": "parametres clavier",
    "comptes": "parametres comptes",
    "timeline": "historique activite",
    # Vague 5 - Securite / DevTools / Maintenance
    "antivirus": "ouvre la securite",
    "defender": "ouvre la securite",
    "firewall": "parametres pare-feu",
    "defrag": "defragmente",
    "hotspot": "active le hotspot",
    "miracast": "partage l'ecran",
    "pilotes": "gestionnaire de peripheriques",
    "drivers": "gestionnaire de peripheriques",
    "peripheriques": "gestionnaire de peripheriques",
    "partitions": "gestionnaire de disques",
    "autostart": "applications demarrage",
    "confidentialite": "parametres confidentialite",
    "desinstaller": "programmes installes",
    # Vague 6 - Personnalisation / Audio
    "imprimante": "parametres imprimantes",
    "wallpaper": "fond d'ecran",
    "polices": "polices",
    "themes": "themes windows",
    "sombre": "active le mode sombre",
    "clair": "active le mode clair",
    "regedit": "ouvre le registre",
    "hdr": "parametres hdr",
    "multitache": "parametres multitache",
    # Vague 7 - Reseau / Systeme avance
    "uptime": "depuis quand le pc tourne",
    "temperature": "temperature cpu",
    "netstat": "connexions actives",
    "sandbox": "ouvre la sandbox",
    "restauration": "restauration systeme",
    "backup": "sauvegarde windows",
    "ethernet": "parametres ethernet",
    "specs": "a propos du pc",
    "mac": "adresse mac",
    "sfc": "verifie les fichiers systeme",
    # Vague 8 - Docker / Git / Dev
    "docker": "liste les conteneurs",
    "conteneurs": "liste les conteneurs",
    "git": "git status",
    "pip": "pip list",
    "jupyter": "ouvre jupyter",
    "notebook": "ouvre jupyter",
    "n8n": "ouvre n8n",
    "workflows": "ouvre n8n",
    "profils wifi": "profils wifi",
    # Vague 9 - Apps / Clipboard / Systeme
    "paint": "ouvre paint",
    "obs": "ouvre obs",
    "vlc": "ouvre vlc",
    "clipboard": "lis le presse-papier",
    "path": "montre le path",
    "archives": "ouvre 7zip",
    "stream": "ouvre obs",
    "dessin": "ouvre paint",
    # Vague 10 - Onglets / Session / Ecrans
    "onglet": "nouvel onglet",
    "tab": "nouvel onglet",
    "hibernation": "hiberne",
    "heure": "quelle heure est-il",
    "date": "quelle date",
    "majuscules": "en majuscules",
    "minuscules": "en minuscules",
    "ecrans": "etends l'ecran",
    "dupliquer": "duplique l'ecran",
    # Vague 11 - Hardware / RAM / CPU
    "ram": "utilisation ram",
    "cpu": "utilisation cpu",
    "processeur": "info cpu",
    "batterie": "niveau de batterie",
    "bios": "info bios",
    "motherboard": "info carte mere",
    "gpu": "info gpu detaille",
    "ssd": "sante des disques",
    "meteo": "dis moi la meteo",
    "logs": "voir les logs",
    # Vague 12 - Chrome / Fenetres / Accessibilite
    "favoris": "ouvre les favoris",
    "bookmarks": "ouvre les favoris",
    "fullscreen": "plein ecran",
    "zoom": "zoom avant",
    "daltonien": "filtre de couleur",
    "captions": "sous-titres",
    # Vague 13 - Reseau avance / DNS / Ports
    "ports": "ports ouverts",
    "arp": "table arp",
    "nslookup": "nslookup",
    "routage": "table de routage",
    "ssl": "certificat ssl",
    "dns": "vide le cache dns",
    "ip publique": "mon ip publique",
    "partages": "partages reseau",
    # Vague 14 - Fichiers avances
    "doublons": "fichiers en double",
    "zip": "compresse",
    "hash": "hash de",
    "grep": "cherche dans les fichiers",
    "recents": "derniers fichiers modifies",
    "gros fichiers": "plus gros fichiers",
}


# ═══════════════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ═══════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove accents, clean punctuation."""
    text = text.lower().strip()
    # Remove common punctuation
    text = re.sub(r"[.,!?;:\"'()\[\]{}<>]", "", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def remove_accents(text: str) -> str:
    """Remove accents from text for fuzzy comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def remove_fillers(text: str) -> str:
    """Remove filler words and politeness from voice input."""
    words = text.split()
    cleaned = []
    skip_next = False
    for i, word in enumerate(words):
        if skip_next:
            skip_next = False
            continue
        # Check single word fillers
        if word in FILLER_WORDS:
            continue
        # Check two-word fillers
        if i < len(words) - 1:
            pair = f"{word} {words[i+1]}"
            if pair in FILLER_WORDS:
                skip_next = True
                continue
        cleaned.append(word)
    return " ".join(cleaned)


def extract_action_intent(text: str) -> str:
    """Extract the core action intent from verbose voice input.

    "est-ce que tu peux ouvrir chrome s'il te plait" → "ouvrir chrome"
    "j'aimerais que tu cherches bitcoin sur google" → "cherche bitcoin sur google"
    """
    text = remove_fillers(text)

    # Remove leading "que tu" / "de"
    text = re.sub(r"^que tu\s+", "", text)
    text = re.sub(r"^de\s+", "", text)

    # Normalize verb forms → imperative
    replacements = [
        (r"\bouvrir\b", "ouvre"),
        (r"\blancer\b", "lance"),
        (r"\bchercher\b", "cherche"),
        (r"\brechercher\b", "recherche"),
        (r"\bnaviguer\b", "navigue"),
        (r"\bfermer\b", "ferme"),
        (r"\bmettre\b", "mets"),
        (r"\baugmenter\b", "augmente"),
        (r"\bbaisser\b", "baisse"),
        (r"\bcouper\b", "coupe"),
        (r"\bverrouiller\b", "verrouille"),
        (r"\beteindre\b", "eteins"),
        (r"\bredemarrer\b", "redemarre"),
        (r"\bscanner\b", "scanne"),
        (r"\bdetecter\b", "detecte"),
        (r"\bafficher\b", "affiche"),
        (r"\bmonter\b", "monte"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════
# PHONETIC SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════

def phonetic_normalize(word: str) -> str:
    """Reduce a French word to its phonetic skeleton."""
    word = remove_accents(word.lower())

    # Apply phonetic reductions
    reductions = [
        (r"eau", "o"), (r"au", "o"), (r"ai", "e"), (r"ei", "e"),
        (r"ou", "u"), (r"ph", "f"), (r"th", "t"), (r"ch", "sh"),
        (r"qu", "k"), (r"gu", "g"), (r"gn", "n"),
        (r"tion", "sion"), (r"ce", "se"), (r"ci", "si"),
        (r"ge", "je"), (r"gi", "ji"),
        # Double consonants → single
        (r"(.)\1+", r"\1"),
        # Silent endings
        (r"[esxzt]$", ""),
    ]
    for pattern, replacement in reductions:
        word = re.sub(pattern, replacement, word)

    return word


def phonetic_similarity(a: str, b: str) -> float:
    """Compare two strings phonetically."""
    pa = phonetic_normalize(a)
    pb = phonetic_normalize(b)
    return SequenceMatcher(None, pa, pb).ratio()


# ═══════════════════════════════════════════════════════════════════════════
# SUGGESTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def get_suggestions(text: str, max_results: int = 3) -> list[tuple[JarvisCommand, float]]:
    """Get command suggestions ranked by combined similarity score.

    Uses: text similarity + phonetic similarity + keyword overlap.
    """
    text_normalized = normalize_text(text)
    text_no_accents = remove_accents(text_normalized)
    text_words = set(text_normalized.split())

    scored: list[tuple[JarvisCommand, float]] = []

    for cmd in COMMANDS:
        best_score = 0.0

        for trigger in cmd.triggers:
            trigger_clean = normalize_text(trigger.replace("{", "").replace("}", ""))
            trigger_no_accents = remove_accents(trigger_clean)
            trigger_words = set(trigger_clean.split())

            # 1. Direct text similarity (40%)
            text_sim = SequenceMatcher(None, text_no_accents, trigger_no_accents).ratio()

            # 2. Phonetic similarity (30%)
            phon_sim = phonetic_similarity(text_normalized, trigger_clean)

            # 3. Keyword overlap (30%)
            if trigger_words:
                common = text_words & trigger_words
                keyword_sim = len(common) / len(trigger_words)
            else:
                keyword_sim = 0.0

            # Combined score
            score = (text_sim * 0.4) + (phon_sim * 0.3) + (keyword_sim * 0.3)
            best_score = max(best_score, score)

        if best_score > 0.30:
            scored.append((cmd, best_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:max_results]


def format_suggestions(suggestions: list[tuple[JarvisCommand, float]]) -> str:
    """Format suggestions for voice output."""
    if not suggestions:
        return "Je n'ai pas compris. Dis 'aide' pour la liste des commandes."

    lines = ["Tu voulais dire:"]
    for i, (cmd, score) in enumerate(suggestions, 1):
        trigger = cmd.triggers[0]
        lines.append(f"  {i}. {trigger} ({cmd.description})")
    lines.append("Repete la commande ou dis le numero.")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# FULL CORRECTION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

async def full_correction_pipeline(
    raw_text: str,
    use_ia: bool = True,
    ia_url: str = "http://127.0.0.1:11434",
    ia_model: str = "qwen3:1.7b",
) -> dict[str, Any]:
    """Complete voice correction pipeline.

    Returns dict with:
    - raw: original text
    - cleaned: after local cleaning
    - corrected: after all corrections
    - intent: extracted action intent
    - command: matched JarvisCommand or None
    - params: extracted parameters
    - confidence: match confidence (0-1)
    - suggestions: alternative commands if low confidence
    - method: how the match was found
    """
    result: dict[str, Any] = {
        "raw": raw_text,
        "cleaned": "",
        "corrected": "",
        "intent": "",
        "command": None,
        "params": {},
        "confidence": 0.0,
        "suggestions": [],
        "method": "none",
    }

    # Step 1: Basic normalization
    cleaned = normalize_text(raw_text)
    result["cleaned"] = cleaned

    # Step 2: Check implicit single-word commands
    single = cleaned.strip()
    if single in IMPLICIT_COMMANDS:
        cleaned = IMPLICIT_COMMANDS[single]
        result["method"] = "implicit"

    # Step 3: Apply local voice corrections dictionary
    corrected = correct_voice_text(cleaned)
    result["corrected"] = corrected

    # Step 4: IA correction EARLY — let LM Studio fix transcription errors FIRST
    ia_corrected = None
    if use_ia:
        try:
            ia_corrected = await _ia_correct(corrected, ia_url, ia_model)
            if ia_corrected and ia_corrected.lower().strip() != corrected.lower().strip():
                result["corrected"] = ia_corrected
                corrected = ia_corrected
        except Exception:
            pass

    # Step 5: Extract action intent (remove fillers, normalize verbs)
    intent = extract_action_intent(corrected)
    result["intent"] = intent

    # Step 6: Try exact/fuzzy match with commands
    from src.commands import match_command
    cmd, params, score = match_command(intent)

    if cmd and score >= 0.70:
        result["command"] = cmd
        result["params"] = params
        result["confidence"] = score
        result["method"] = "ia_direct" if ia_corrected else "direct"
        return result

    # Step 7: Try phonetic matching
    best_phon_cmd = None
    best_phon_score = 0.0
    for c in COMMANDS:
        for trigger in c.triggers:
            clean_trigger = normalize_text(trigger.replace("{", "").replace("}", ""))
            ps = phonetic_similarity(intent, clean_trigger)
            if ps > best_phon_score:
                best_phon_score = ps
                best_phon_cmd = c

    if best_phon_cmd and best_phon_score >= 0.70:
        result["command"] = best_phon_cmd
        result["params"] = {}
        result["confidence"] = best_phon_score
        result["method"] = "phonetic"
        return result

    # Step 8: If IA corrected but still no match, try matching the IA intent directly
    if ia_corrected:
        ia_intent = extract_action_intent(ia_corrected)
        if ia_intent != intent:
            cmd3, params3, score3 = match_command(ia_intent)
            if cmd3 and score3 >= 0.55:
                result["command"] = cmd3
                result["params"] = params3
                result["confidence"] = score3
                result["method"] = "ia_rematch"
                return result

    # Step 9: Get suggestions
    suggestions = get_suggestions(intent)
    result["suggestions"] = suggestions

    if suggestions and suggestions[0][1] >= 0.55:
        top_cmd, top_score = suggestions[0]
        result["command"] = top_cmd
        result["confidence"] = top_score
        result["method"] = "suggestion"
        return result

    # No match — will be sent to Claude as freeform
    result["confidence"] = max(score, best_phon_score)
    result["method"] = "freeform"
    return result


async def _ia_correct(text: str, url: str, model: str) -> str:
    """Use Ollama qwen3:1.7b (fast, 1.36 GB) to correct voice transcription.

    Primary: Ollama qwen3:1.7b (lightweight, always loaded, <1s)
    Fallback: LM Studio M1/qwen3-30b (heavier but more accurate)
    """
    import httpx
    from src.config import config
    prompt = (
        "Tu es le correcteur ORTHOGRAPHIQUE de JARVIS.\n"
        "REGLE ABSOLUE: corrige UNIQUEMENT les fautes d'orthographe et de grammaire.\n"
        "NE CHANGE JAMAIS le sens, NE RAJOUTE JAMAIS de mots, NE MODIFIE PAS l'intention.\n"
        "Exemples:\n"
        "- 'ouvre moa les chart mexc' → 'ouvre moi les charts mexc'\n"
        "- 'ferm tout les fenaitre' → 'ferme toutes les fenetres'\n"
        "- 'statu du clusteur' → 'statut du cluster'\n"
        "- 'repete' → 'repete'\n"
        "- 'ouvre youtube' → 'ouvre youtube'\n"
        "- 'mets youtube' → 'mets youtube'\n"
        "- 'kel heurre il ait' → 'quelle heure il est'\n"
        "Reponds UNIQUEMENT avec le texte corrige, RIEN d'autre. Pas de /no_think.\n\n"
        f"Texte: {text}"
    )
    messages = [{"role": "user", "content": prompt}]
    # Primary: Ollama qwen3:1.7b (fast, lightweight, always available)
    ol = config.get_ollama_node("OL1")
    if ol:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.post(
                    f"{ol.url}/api/chat",
                    json={
                        "model": model, "messages": messages,
                        "stream": False, "think": False,
                        "options": {"temperature": 0.1, "num_predict": 200},
                    },
                )
                r.raise_for_status()
                return r.json()["message"]["content"].strip()
        except Exception:
            pass
    # Fallback: LM Studio M1 (qwen3-30b — heavier but accurate)
    node = config.get_node("M1")
    if node:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.post(
                    f"{node.url}/api/v1/chat",
                    json={"model": node.default_model, "input": text, "system_prompt": messages[0]["content"] if messages and messages[0]["role"] == "system" else "", "temperature": 0.1, "max_output_tokens": 200, "stream": False, "store": False},
                )
                r.raise_for_status()
                from src.tools import extract_lms_output
                return extract_lms_output(r.json()).strip()
        except Exception:
            pass
    return text


# ═══════════════════════════════════════════════════════════════════════════
# VOICE SESSION STATE — Track conversation context
# ═══════════════════════════════════════════════════════════════════════════

class VoiceSession:
    """Track voice session state for multi-turn correction."""

    def __init__(self):
        self.last_suggestions: list[tuple[JarvisCommand, float]] = []
        self.last_raw: str = ""
        self.correction_count: int = 0
        self.history: list[str] = []

    def is_selecting_suggestion(self, text: str) -> JarvisCommand | None:
        """Check if user is selecting from previous suggestions by number."""
        text = text.strip()
        if text in ("1", "un", "premier", "premiere", "la premiere", "le premier"):
            idx = 0
        elif text in ("2", "deux", "deuxieme", "la deuxieme", "le deuxieme"):
            idx = 1
        elif text in ("3", "trois", "troisieme", "la troisieme", "le troisieme"):
            idx = 2
        else:
            return None

        if idx < len(self.last_suggestions):
            return self.last_suggestions[idx][0]
        return None

    def is_confirmation(self, text: str) -> bool:
        """Check if user is confirming."""
        confirms = {"oui", "yes", "ok", "confirme", "valide", "go", "lance", "d'accord", "daccord", "ouais", "yep", "correct", "exactement", "c'est ca"}
        return text.strip().lower() in confirms

    def is_denial(self, text: str) -> bool:
        """Check if user is denying/canceling."""
        denials = {"non", "no", "annule", "annuler", "pas ca", "non merci", "nan", "nope", "stop", "arrete"}
        return text.strip().lower() in denials

    def add_to_history(self, text: str):
        """Add corrected text to history for context."""
        self.history.append(text)
        if len(self.history) > 10:
            self.history.pop(0)
