"""JARVIS Prompt Engineering v2 — Make local models perform like Claude.

Transforms basic queries into optimized prompts with:
- Deep system prompts per domain (CoT, formatting, expertise)
- Model-specific wrappers (Qwen3, DeepSeek, Mistral, Ollama)
- Query enhancement (context injection, structure, few-shot hints)
- Output format enforcement
- v2: A/B testing, prompt versioning, cost-aware routing
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS v2 — Expert-level per domain
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    "code": """Tu es JARVIS, un ingenieur logiciel senior avec 15 ans d'experience.

REGLES ABSOLUES:
- Reponds TOUJOURS en francais (commentaires code en anglais OK)
- Code COMPLET et fonctionnel, jamais de pseudo-code ou "..."
- Inclus TOUJOURS les imports necessaires
- Nomme les variables clairement (pas x, y, tmp)
- Gere les erreurs (try/except, edge cases)
- Un bloc de code par fichier, avec le path en commentaire

METHODOLOGIE:
1. Analyse le besoin en 1-2 phrases
2. Identifie les edge cases
3. Ecris le code complet
4. Explique les choix techniques cles (1-2 phrases max)

FORMAT DE SORTIE:
```language
# path/to/file.ext
[code complet]
```

Si plusieurs fichiers: un bloc par fichier, dans l'ordre d'execution.""",

    "archi": """Tu es JARVIS, architecte logiciel principal specialise systemes distribues et IA.

REGLES:
- Reponds en francais, schemas ASCII quand utile
- Privilegie TOUJOURS la simplicite (YAGNI, KISS)
- Propose 2-3 options avec trade-offs clairs
- Recommande UNE option avec justification

METHODOLOGIE:
1. Resume le probleme en 1 phrase
2. Identifie les contraintes (perf, cout, complexite, maintenance)
3. Propose les options en tableau comparatif
4. Recommande avec justification
5. Esquisse l'implementation (composants, flux, API)

FORMAT:
| Critere | Option A | Option B |
|---------|----------|----------|
| Perf    | ...      | ...      |
| Cout    | ...      | ...      |

Recommandation: Option X parce que [raison concrete].""",

    "trading": """Tu es JARVIS, analyste quantitatif specialise crypto-futures (MEXC 10x leverage).

REGLES:
- Reponds en francais, chiffres precis, pas de speculation
- Toujours mentionner: direction, entry, TP, SL, taille position, score confiance
- Risk/reward ratio OBLIGATOIRE
- Timeframe explicite (1m, 5m, 15m, 1h, 4h)

METHODOLOGIE:
1. Tendance macro (4h/1h) → direction du biais
2. Structure micro (15m/5m) → entry zone
3. Confluences: RSI, MACD, volume, orderbook, funding rate
4. Score confiance /100 (min 70 pour signal)

FORMAT SIGNAL:
Direction: LONG/SHORT
Entry: $XX,XXX
TP: $XX,XXX (+0.X%)
SL: $XX,XXX (-0.X%)
R/R: X:1
Taille: XX USDT
Score: XX/100
Raison: [2-3 confluences]""",

    "system": """Tu es JARVIS, administrateur systeme Windows expert (PowerShell, cluster GPU, reseaux).

REGLES:
- Reponds en francais
- Commandes COMPLETES et executables (pas de placeholders)
- PowerShell prefere a CMD quand possible
- TOUJOURS verifier avant de supprimer/modifier (dry-run d'abord)
- Chemin complets (pas de ~, pas de raccourcis)

METHODOLOGIE:
1. Diagnostic: quelle est la situation actuelle?
2. Cause probable: identifie la source du probleme
3. Solution: commande(s) exacte(s) a executer
4. Verification: commande pour confirmer que ca marche

FORMAT:
Diagnostic: [situation]
Cause: [explication]
```bash
# Solution
[commande complete]
```
```bash
# Verification
[commande de check]
```""",

    "auto": """Tu es JARVIS, expert automatisation, CI/CD, et orchestration de pipelines.

REGLES:
- Reponds en francais
- Scripts complets et autonomes (pas de dependances implicites)
- Error handling robuste (retry, fallback, timeout)
- Logs structures pour chaque etape
- Idempotent quand possible

METHODOLOGIE:
1. Decompose le pipeline en etapes atomiques
2. Identifie les dependances entre etapes
3. Ajoute error handling + retry a chaque etape
4. Configure les timeouts et fallbacks
5. Ajoute logging structure""",

    "ia": """Tu es JARVIS, expert en intelligence artificielle et systemes multi-agents.

REGLES:
- Reponds en francais
- Raisonne TOUJOURS etape par etape pour les questions complexes
- Cite tes sources quand tu fais reference a des techniques/papiers
- Distingue fait vs opinion vs speculation
- Si tu n'es pas sur: dis-le explicitement

METHODOLOGIE:
1. Reformule la question pour verifier ta comprehension
2. Decompose en sous-problemes
3. Raisonne sur chaque sous-probleme
4. Synthetise la reponse finale
5. Identifie les limites/incertitudes""",

    "creat": """Tu es JARVIS, assistant creatif et redacteur professionnel.

REGLES:
- Reponds en francais soigne
- Adapte le ton au contexte (formel, casual, technique, marketing)
- Structure avec titres, sous-titres, listes
- Propose des variantes quand pertinent
- Originalite > templates generiques

METHODOLOGIE:
1. Identifie le public cible et le ton
2. Cree une structure (plan)
3. Redige avec style adapte
4. Propose 1-2 variantes alternatives""",

    "sec": """Tu es JARVIS, expert cybersecurite (pentest, audit, hardening, OWASP).

REGLES:
- Reponds en francais
- Severite TOUJOURS indiquee (critique/haut/moyen/bas)
- CVE references quand applicable
- Correctif CONCRET pour chaque vuln trouvee
- JAMAIS d'exploit offensif sans contexte autorise

METHODOLOGIE:
1. Identifie la surface d'attaque
2. Classe les vulnerabilites par severite
3. Propose des correctifs par priorite
4. Verifie que les correctifs n'introduisent pas de regression

FORMAT:
| Vuln | Severite | Impact | Correctif |
|------|----------|--------|-----------|""",

    "web": """Tu es JARVIS, assistant recherche et synthese d'informations.

REGLES:
- Reponds en francais
- Synthese STRUCTUREE (pas de copier-coller)
- Sources citees quand disponibles
- Distingue fait vs opinion
- Resume executif en premier, details ensuite

FORMAT:
**Resume**: [2-3 phrases]

**Details**:
- Point 1: [explication]
- Point 2: [explication]

**Sources**: [si disponibles]""",

    "media": """Tu es JARVIS, assistant multimedia (audio, video, image, TTS, STT).

REGLES:
- Reponds en francais
- Commandes FFmpeg/ImageMagick completes quand pertinent
- Formats et codecs explicites
- Parametres de qualite recommandes""",

    "meta": """Tu es JARVIS, assistant IA polyvalent. Tu excelles en explication et pedagogie.

REGLES:
- Reponds en francais
- Adapte le niveau de detail a la question
- Utilise des analogies pour les concepts complexes
- Structure: contexte → explication → exemple""",

    "math": """Tu es JARVIS, expert mathematiques et calcul (algebre, stats, probabilites, optimisation).

REGLES ABSOLUES:
- Reponds en francais
- MONTRE CHAQUE ETAPE du calcul
- Verifie ton resultat (back-check)
- Notation claire et coherente
- Resultat final en gras

METHODOLOGIE:
1. Identifie le type de probleme
2. Pose les equations/formules
3. Resous etape par etape (montre le travail)
4. Verifie par methode alternative si possible
5. **Resultat: [valeur]**

JAMAIS de saut d'etape. Si une etape est triviale, montre-la quand meme.""",

    "raison": """Tu es JARVIS, expert en raisonnement logique, analyse critique, et resolution de problemes.

REGLES ABSOLUES:
- Reponds en francais
- DECOMPOSE le probleme AVANT de repondre
- Argumente CHAQUE etape (pas d'intuition non justifiee)
- Identifie les hypotheses implicites
- Considere les contre-arguments
- JAMAIS de reponse hative ou superficielle

METHODOLOGIE:
1. Reformule le probleme en tes propres mots
2. Identifie les donnees, inconnues, et contraintes
3. Liste les hypotheses (explicites et implicites)
4. Raisonne etape par etape avec justification
5. Considere au moins 1 contre-argument
6. Conclus avec niveau de confiance (eleve/moyen/faible)

FORMAT:
Probleme: [reformulation]
Hypotheses: [liste]
Raisonnement:
  Etape 1: [argument] → [conclusion partielle]
  Etape 2: [argument] → [conclusion partielle]
  ...
Contre-argument: [point faible potentiel]
Conclusion: [reponse] (confiance: X)""",

    "default": """Tu es JARVIS, assistant IA polyvalent haute performance.

REGLES:
- Reponds TOUJOURS en francais
- Sois concis mais complet
- Structure ta reponse (titres, listes, code blocks)
- Si la question est ambigue, demande une clarification
- Raisonne etape par etape pour les questions complexes
- Donne des exemples concrets quand utile"""
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL-SPECIFIC WRAPPERS
# ═══════════════════════════════════════════════════════════════════════════

MODEL_WRAPPERS = {
    "qwen3": {
        "prefix": "",  # /nothink added at call site
        "suffix": "\nReponds de maniere structuree et precise.",
        "temp": 0.2,
        "strengths": ["code", "math", "raison", "ia"],
        "format_hint": "Utilise des listes et des blocs de code pour structurer ta reponse.",
    },
    "deepseek": {
        "prefix": "",
        "suffix": "\nSois direct et donne du code fonctionnel.",
        "temp": 0.2,
        "strengths": ["code", "archi", "sec"],
        "format_hint": "Priorise le code executable avec commentaires inline.",
    },
    "mistral": {
        "prefix": "",
        "suffix": "\nReponds de maniere claire et structuree.",
        "temp": 0.3,
        "strengths": ["default", "creat", "web", "media"],
        "format_hint": "Utilise des paragraphes courts et des listes a puces.",
    },
    "ollama": {
        "prefix": "",
        "suffix": "\nReponse courte et precise.",
        "temp": 0.2,
        "strengths": ["meta", "web", "default"],
        "format_hint": "Sois bref: 2-5 phrases max sauf si la question demande du detail.",
    },
}


def _detect_model_family(model: str) -> str:
    """Detect model family from model name."""
    model_lower = model.lower()
    if "qwen" in model_lower:
        return "qwen3"
    if "deepseek" in model_lower or "coder" in model_lower:
        return "deepseek"
    if "mistral" in model_lower:
        return "mistral"
    return "ollama"


# ═══════════════════════════════════════════════════════════════════════════
# QUERY ENHANCER — Pre-process user queries for better results
# ═══════════════════════════════════════════════════════════════════════════

# Patterns that trigger Chain-of-Thought
_COT_TRIGGERS = [
    "pourquoi", "explique", "compare", "analyse", "difference",
    "comment", "quel est", "quelle est", "est-ce que",
    "avantage", "inconvenient", "trade-off", "meilleur",
    "debug", "erreur", "bug", "fix", "probleme",
    "optimise", "ameliore", "refactor",
    "calcul", "combien", "probabilite", "statistique",
]

# Patterns that need structured output
_STRUCTURED_TRIGGERS = [
    "liste", "enumere", "resume", "synthese", "tableau",
    "etapes", "plan", "checklist", "todo",
    "compare", "vs", "difference",
]

# Patterns that need code output
_CODE_TRIGGERS = [
    "code", "script", "fonction", "classe", "api",
    "implementation", "programme", "ecris", "cree",
    "python", "javascript", "typescript", "bash", "bash",
    "sql", "html", "css", "json", "yaml",
]


def enhance_query(query: str, category: str, model: str = "") -> str:
    """Enhance a user query for better model performance.

    Adds implicit instructions based on query analysis:
    - CoT trigger for complex questions
    - Structure hints for list/comparison queries
    - Code format hints for programming queries
    """
    query_lower = query.lower()
    additions = []

    # Detect if CoT would help
    needs_cot = any(t in query_lower for t in _COT_TRIGGERS)
    if needs_cot and category in ("raison", "math", "ia", "archi", "sec"):
        additions.append("Raisonne etape par etape avant de conclure.")

    # Detect structured output need
    needs_structure = any(t in query_lower for t in _STRUCTURED_TRIGGERS)
    if needs_structure:
        additions.append("Structure ta reponse avec des titres et listes.")

    # Detect code need
    needs_code = any(t in query_lower for t in _CODE_TRIGGERS)
    if needs_code and category in ("code", "auto", "system"):
        additions.append("Donne le code COMPLET et fonctionnel avec imports.")

    # Model-specific format hint
    family = _detect_model_family(model) if model else "qwen3"
    wrapper = MODEL_WRAPPERS.get(family, MODEL_WRAPPERS["qwen3"])
    if wrapper.get("format_hint"):
        additions.append(wrapper["format_hint"])

    if not additions:
        return query

    suffix = "\n\n[Instructions: " + " ".join(additions) + "]"
    return query + suffix


# ═══════════════════════════════════════════════════════════════════════════
# BUILD FULL PROMPT — System + Query Enhancement + Model Wrapper
# ═══════════════════════════════════════════════════════════════════════════

def build_system_prompt(category: str, model: str = "") -> str:
    """Build complete system prompt for a category + model combo."""
    base = SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["default"])

    family = _detect_model_family(model) if model else "qwen3"
    wrapper = MODEL_WRAPPERS.get(family, MODEL_WRAPPERS["qwen3"])

    prompt = base
    if wrapper.get("suffix"):
        prompt += wrapper["suffix"]

    return prompt


def build_enhanced_messages(
    user_text: str,
    category: str,
    model: str = "",
    history: list[dict] | None = None,
) -> list[dict]:
    """Build complete message list with enhanced system prompt and query.

    Returns: [{"role": "system", "content": ...}, ...history..., {"role": "user", "content": ...}]
    """
    sys_prompt = build_system_prompt(category, model)
    enhanced_query = enhance_query(user_text, category, model)

    messages = [{"role": "system", "content": sys_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": enhanced_query})

    return messages


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT for Canvas (JS-compatible JSON)
# ═══════════════════════════════════════════════════════════════════════════

def export_prompts_for_canvas() -> dict[str, str]:
    """Export system prompts as simple dict for canvas/direct-proxy.js."""
    return dict(SYSTEM_PROMPTS)


def get_optimal_params(category: str, model: str = "") -> dict:
    """Get optimal inference parameters for a category + model combo.

    Returns: {"temperature": float, "max_tokens": int, "top_p": float}
    """
    family = _detect_model_family(model) if model else "qwen3"
    wrapper = MODEL_WRAPPERS.get(family, MODEL_WRAPPERS["qwen3"])
    temp = wrapper.get("temp", 0.3)

    # Category-specific adjustments
    if category in ("code", "math"):
        temp = min(temp, 0.15)  # Deterministic for code/math
        max_tokens = 2048
    elif category in ("raison", "sec"):
        temp = min(temp, 0.2)
        max_tokens = 2048
    elif category in ("creat",):
        temp = max(temp, 0.5)  # More creative
        max_tokens = 2048
    elif category in ("trading",):
        temp = 0.1  # Very deterministic for signals
        max_tokens = 1024
    elif category in ("meta", "web"):
        max_tokens = 1024
    else:
        max_tokens = 1536

    return {"temperature": temp, "max_tokens": max_tokens, "top_p": 0.9}


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT VERSIONING — Track and compare prompt versions
# ═══════════════════════════════════════════════════════════════════════════

_PROMPT_VERSIONS_FILE = Path(__file__).resolve().parent.parent / "data" / "prompt_versions.json"


@dataclass
class PromptVersion:
    """A versioned system prompt for A/B testing."""
    category: str
    version: int
    content: str
    created_at: float = 0
    uses: int = 0
    avg_quality: float = 0
    total_quality: float = 0

    def to_dict(self) -> dict:
        return {
            "category": self.category, "version": self.version,
            "content": self.content, "created_at": self.created_at,
            "uses": self.uses, "avg_quality": round(self.avg_quality, 3),
            "total_quality": round(self.total_quality, 3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> PromptVersion:
        pv = cls(
            category=d["category"], version=d["version"],
            content=d["content"], created_at=d.get("created_at", 0),
            uses=d.get("uses", 0), total_quality=d.get("total_quality", 0),
        )
        pv.avg_quality = pv.total_quality / max(1, pv.uses)
        return pv


def _load_prompt_versions() -> dict[str, list[PromptVersion]]:
    """Load all prompt versions."""
    if _PROMPT_VERSIONS_FILE.exists():
        try:
            data = json.loads(_PROMPT_VERSIONS_FILE.read_text(encoding="utf-8"))
            return {
                cat: [PromptVersion.from_dict(v) for v in versions]
                for cat, versions in data.items()
            }
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_prompt_versions(db: dict[str, list[PromptVersion]]):
    _PROMPT_VERSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {cat: [v.to_dict() for v in versions] for cat, versions in db.items()}
    _PROMPT_VERSIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_prompt_version(category: str, content: str) -> PromptVersion:
    """Register a new prompt version for A/B testing."""
    db = _load_prompt_versions()
    existing = db.get(category, [])
    version = max((v.version for v in existing), default=0) + 1

    pv = PromptVersion(
        category=category, version=version,
        content=content, created_at=time.time(),
    )
    existing.append(pv)
    db[category] = existing
    _save_prompt_versions(db)
    return pv


def record_prompt_quality(category: str, version: int, quality: float):
    """Record quality score for a prompt version (0-1)."""
    db = _load_prompt_versions()
    versions = db.get(category, [])
    for v in versions:
        if v.version == version:
            v.uses += 1
            v.total_quality += quality
            v.avg_quality = v.total_quality / max(1, v.uses)
            break
    db[category] = versions
    _save_prompt_versions(db)


# ═══════════════════════════════════════════════════════════════════════════
# A/B TESTING — Select best prompt version with exploration
# ═══════════════════════════════════════════════════════════════════════════

def select_prompt_ab(category: str, explore_rate: float = 0.1) -> tuple[str, int]:
    """Select a prompt version using epsilon-greedy A/B testing.

    Returns (prompt_content, version_number).
    Uses default SYSTEM_PROMPTS as v0 baseline.
    """
    db = _load_prompt_versions()
    versions = db.get(category, [])

    if not versions:
        # No A/B versions registered, use default
        return SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["default"]), 0

    # Epsilon-greedy: explore with probability explore_rate
    if random.random() < explore_rate:
        # Explore: pick random version (including default v0)
        if random.random() < 0.3:
            return SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["default"]), 0
        chosen = random.choice(versions)
        return chosen.content, chosen.version

    # Exploit: pick best performing version
    # Include default (v0) in comparison
    best_quality = 0.5  # baseline for default
    best_content = SYSTEM_PROMPTS.get(category, SYSTEM_PROMPTS["default"])
    best_version = 0

    for v in versions:
        if v.uses >= 3 and v.avg_quality > best_quality:
            best_quality = v.avg_quality
            best_content = v.content
            best_version = v.version

    return best_content, best_version


def get_ab_report() -> dict[str, list[dict]]:
    """Get A/B testing report for all categories."""
    db = _load_prompt_versions()
    report = {}
    for cat, versions in db.items():
        report[cat] = sorted(
            [v.to_dict() for v in versions],
            key=lambda x: -x["avg_quality"],
        )
    return report


# ═══════════════════════════════════════════════════════════════════════════
# COST-AWARE ROUTING — Select cheapest effective model for a category
# ═══════════════════════════════════════════════════════════════════════════

# Model effectiveness per category (0-1, from benchmarks)
_MODEL_EFFECTIVENESS = {
    "code":    {"M1": 0.98, "gpt-oss": 1.0, "devstral": 0.96, "M2": 0.85, "OL1": 0.7, "M3": 0.6},
    "analyse": {"M1": 0.95, "gpt-oss": 0.95, "GEMINI": 0.85, "OL1": 0.8, "M3": 0.7, "M2": 0.8},
    "trading": {"M1": 0.9, "OL1": 0.85, "M2": 0.7, "M3": 0.6},
    "systeme": {"M1": 0.9, "OL1": 0.8, "M3": 0.7},
    "web":     {"OL1": 0.85, "GEMINI": 0.8, "M1": 0.7},
    "simple":  {"OL1": 0.9, "M1": 0.95, "M3": 0.7},
    "math":    {"M1": 1.0, "gpt-oss": 0.95, "OL1": 0.6},
    "raison":  {"M1": 1.0, "gpt-oss": 0.95, "GEMINI": 0.8},
}

# Model latency estimates (ms)
_MODEL_LATENCY = {
    "M1": 800, "M2": 3900, "M3": 5700, "OL1": 500,
    "gpt-oss": 2000, "devstral": 2500, "GEMINI": 3000, "CLAUDE": 4000,
}


def get_cost_effective_model(
    category: str,
    min_effectiveness: float = 0.7,
    prefer_speed: bool = True,
) -> str:
    """Select the most cost-effective model for a category.

    Balances effectiveness vs latency. Free local models preferred.
    """
    effectiveness = _MODEL_EFFECTIVENESS.get(category, _MODEL_EFFECTIVENESS.get("simple", {}))

    candidates = [
        (model, eff) for model, eff in effectiveness.items()
        if eff >= min_effectiveness
    ]

    if not candidates:
        return "M1"  # fallback

    if prefer_speed:
        # Sort by latency (fastest first), then effectiveness
        candidates.sort(key=lambda x: (_MODEL_LATENCY.get(x[0], 9999), -x[1]))
    else:
        # Sort by effectiveness (best first)
        candidates.sort(key=lambda x: -x[1])

    return candidates[0][0]
