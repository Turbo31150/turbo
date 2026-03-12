#!/usr/bin/env python3
"""linkedin_content_generator.py — Generate optimized LinkedIn content via cluster AI.

Pipeline:
  1. CLASSIFY: Identify theme, keywords, hashtags (M1, fast)
  2. GENERATE FR: Optimized French LinkedIn post (gpt-oss, quality)
  3. TRANSLATE EN: Native English version (M1/devstral, parallel)
  4. COMMENTS x3: Strategic comment angles (gpt-oss, parallel)
  5. FORMAT + DELIVER: JSON output + Telegram + etoile.db

CLI:
    --idea "your raw idea"     : Generate content from idea
    --topic "AI automation"    : Topic/sector for targeting
    --tone expert|inspiring|provocateur : Writing tone (default: expert)
    --once                     : Single generation cycle
    --dry-run                  : Show prompts without calling agents

Stdlib-only (json, argparse, urllib, sqlite3, time).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT

# --- Agent endpoints (auto-fallback: M1 > OL1 > minimax > M2 > M3) ---
AGENTS = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "model": "qwen3-8b",
        "type": "lmstudio",
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "type": "ollama",
    },
    "minimax": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "minimax-m2.5:cloud",
        "type": "ollama",
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "type": "lmstudio",
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "type": "lmstudio",
    },
}

# --- Prompts ---
PROMPT_CLASSIFY = """Analyse cette idee pour un post LinkedIn.
Reponds en JSON strict (pas de markdown) avec:
{{"theme": "...", "keywords": ["k1","k2","k3","k4","k5"], "hashtags": ["#h1","#h2","#h3","#h4","#h5"], "target_audience": "...", "best_posting_time": "HH:MM", "content_type": "carousel|text|video|poll"}}

Idee: {idea}
Secteur cible: {topic}"""

PROMPT_POST_FR = """Tu es un expert LinkedIn avec 50K+ followers. Genere un post LinkedIn VIRAL en francais.

REGLES:
- Hook percutant (premiere ligne qui arrete le scroll)
- Corps structure avec sauts de ligne (pas de mur de texte)
- Storytelling ou donnees concretes (chiffres, pourcentages)
- CTA (call-to-action) en fin de post
- Max 3000 caracteres
- Ton: {tone}
- PAS de formatage markdown, juste du texte brut avec sauts de ligne

THEME: {theme}
MOTS-CLES: {keywords}
AUDIENCE: {audience}
IDEE BRUTE: {idea}

Genere UNIQUEMENT le post (pas de commentaire ni explication)."""

PROMPT_POST_EN = """You are a LinkedIn expert with 50K+ followers. Translate and ADAPT this French LinkedIn post to English.

RULES:
- NOT a word-for-word translation — adapt idioms, references, tone
- Keep the hook impactful in English
- Maintain the same structure and CTA
- Max 3000 characters
- Plain text only (no markdown)

FRENCH POST:
{post_fr}

Generate ONLY the English post (no commentary)."""

PROMPT_COMMENTS = """Tu es un professionnel reconnu dans le secteur "{topic}". Genere 3 commentaires strategiques LinkedIn differents.

Chaque commentaire sera utilise pour commenter des posts d'autres personnes sur LinkedIn, afin de gagner en visibilite.

REGLES PAR COMMENTAIRE:
- 50-150 mots chacun
- Apporte de la VALEUR (pas juste "super post!")
- 3 angles differents: 1) Partage d'experience, 2) Ajout de donnees/stats, 3) Question pertinente
- Ton professionnel mais humain
- PAS de hashtags dans les commentaires

THEME: {theme}
MOTS-CLES: {keywords}

Reponds en JSON strict:
{{"comments": [{{"angle": "experience", "text": "..."}}, {{"angle": "data", "text": "..."}}, {{"angle": "question", "text": "..."}}]}}"""


def call_agent(agent_name, prompt, timeout=120):
    """Call a cluster agent and return the response text."""
    agent = AGENTS.get(agent_name)
    if not agent:
        return None

    try:
        if agent["type"] == "ollama":
            body = json.dumps({
                "model": agent["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }).encode()
            req = urllib.request.Request(agent["url"], body,
                                        {"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")

        elif agent["type"] == "lmstudio":
            # /nothink only for qwen3 models, not deepseek-r1
            is_reasoning = "deepseek" in agent["model"]
            prefix = "" if is_reasoning else "/nothink\n"
            body = json.dumps({
                "model": agent["model"],
                "input": f"{prefix}{prompt}",
                "temperature": 0.3,
                "max_output_tokens": 4096,
                "stream": False,
                "store": False,
            }).encode()
            req = urllib.request.Request(agent["url"], body,
                                        {"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            data = json.loads(resp.read())
            # Extract last message block from output
            for block in reversed(data.get("output", [])):
                if block.get("type") == "message":
                    for c in block.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "")
            return str(data.get("output", ""))

    except Exception as e:
        print(f"  [WARN] {agent_name} failed: {e}")
        return None


def call_with_fallback(agents_list, prompt, timeout=120):
    """Try agents in order, return first success."""
    for name in agents_list:
        print(f"  Trying {name}...", end=" ", flush=True)
        t0 = time.time()
        result = call_agent(name, prompt, timeout)
        dt = time.time() - t0
        if result and len(result.strip()) > 20:
            print(f"OK ({dt:.1f}s, {len(result)} chars)")
            return result, name
        print(f"SKIP ({dt:.1f}s)")
    return None, None


def parse_json_safe(text):
    """Extract JSON from text that may contain markdown fences."""
    if not text:
        return None
    # Strip markdown fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None


def save_to_db(result):
    """Save generated content to etoile.db for analytics."""
    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS linkedin_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        idea TEXT,
        topic TEXT,
        tone TEXT,
        theme TEXT,
        post_fr TEXT,
        post_en TEXT,
        comments_json TEXT,
        hashtags TEXT,
        agents_used TEXT,
        generation_time_s REAL,
        status TEXT DEFAULT 'generated'
    )""")
    db.execute("""INSERT INTO linkedin_content
        (timestamp, idea, topic, tone, theme, post_fr, post_en,
         comments_json, hashtags, agents_used, generation_time_s)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(),
         result.get("idea", ""),
         result.get("topic", ""),
         result.get("tone", ""),
         result.get("theme", ""),
         result.get("post_fr", ""),
         result.get("post_en", ""),
         json.dumps(result.get("comments", []), ensure_ascii=False),
         json.dumps(result.get("hashtags", []), ensure_ascii=False),
         json.dumps(result.get("agents_used", []), ensure_ascii=False),
         result.get("generation_time_s", 0)))
    db.commit()
    db.close()


def send_telegram(text):
    """Send notification to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT,
        "text": text[:4000],
        "parse_mode": "HTML",
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def generate_content(idea, topic="tech/IA", tone="expert", dry_run=False):
    """Main pipeline: idea → post FR + EN + 3 comments."""
    t_start = time.time()
    result = {"idea": idea, "topic": topic, "tone": tone, "agents_used": []}

    # --- STEP 1: Classify ---
    print("\n[1/5] Classification...")
    prompt = PROMPT_CLASSIFY.format(idea=idea, topic=topic)
    if dry_run:
        print(f"  PROMPT: {prompt[:200]}...")
        classify = {"theme": topic, "keywords": [], "hashtags": [],
                     "target_audience": "pros", "best_posting_time": "08:30",
                     "content_type": "text"}
    else:
        raw, agent = call_with_fallback(["M1", "OL1", "minimax"], prompt, timeout=30)
        classify = parse_json_safe(raw) or {
            "theme": topic, "keywords": [topic],
            "hashtags": [f"#{topic.replace(' ', '')}"],
            "target_audience": "professionnels tech",
            "best_posting_time": "08:30", "content_type": "text"}
        if agent:
            result["agents_used"].append(f"classify:{agent}")

    result["theme"] = classify.get("theme", topic)
    result["hashtags"] = classify.get("hashtags", [])
    result["keywords"] = classify.get("keywords", [])
    result["target_audience"] = classify.get("target_audience", "")
    result["best_posting_time"] = classify.get("best_posting_time", "08:30")
    result["content_type"] = classify.get("content_type", "text")
    print(f"  Theme: {result['theme']}")
    print(f"  Keywords: {', '.join(result['keywords'][:5])}")
    print(f"  Hashtags: {' '.join(result['hashtags'][:5])}")

    # --- STEP 2: Generate FR post ---
    print("\n[2/5] Generation post FR...")
    prompt = PROMPT_POST_FR.format(
        tone=tone, theme=result["theme"],
        keywords=", ".join(result["keywords"]),
        audience=result["target_audience"], idea=idea)
    if dry_run:
        print(f"  PROMPT: {prompt[:200]}...")
        result["post_fr"] = "[DRY RUN — post FR]"
    else:
        post_fr, agent = call_with_fallback(
            ["M1", "minimax", "OL1", "M2"], prompt, timeout=120)
        result["post_fr"] = (post_fr or "").strip()
        if agent:
            result["agents_used"].append(f"post_fr:{agent}")
    print(f"  Post FR: {len(result['post_fr'])} chars")

    # --- STEP 3: Translate EN ---
    print("\n[3/5] Traduction EN...")
    prompt = PROMPT_POST_EN.format(post_fr=result["post_fr"])
    if dry_run:
        print(f"  PROMPT: {prompt[:200]}...")
        result["post_en"] = "[DRY RUN — post EN]"
    else:
        post_en, agent = call_with_fallback(
            ["M1", "minimax", "OL1", "M2"], prompt, timeout=120)
        result["post_en"] = (post_en or "").strip()
        if agent:
            result["agents_used"].append(f"post_en:{agent}")
    print(f"  Post EN: {len(result['post_en'])} chars")

    # --- STEP 4: Strategic comments ---
    print("\n[4/5] Generation commentaires strategiques...")
    prompt = PROMPT_COMMENTS.format(
        topic=topic, theme=result["theme"],
        keywords=", ".join(result["keywords"]))
    if dry_run:
        print(f"  PROMPT: {prompt[:200]}...")
        result["comments"] = [
            {"angle": "experience", "text": "[DRY RUN]"},
            {"angle": "data", "text": "[DRY RUN]"},
            {"angle": "question", "text": "[DRY RUN]"},
        ]
    else:
        raw, agent = call_with_fallback(
            ["minimax", "M1", "OL1", "M2"], prompt, timeout=120)
        parsed = parse_json_safe(raw)
        if parsed and "comments" in parsed:
            result["comments"] = parsed["comments"]
        else:
            result["comments"] = [{"angle": "raw", "text": (raw or "")[:500]}]
        if agent:
            result["agents_used"].append(f"comments:{agent}")
    print(f"  Comments: {len(result['comments'])} generated")

    # --- STEP 5: Format + Deliver ---
    print("\n[5/5] Finalisation...")
    result["generation_time_s"] = round(time.time() - t_start, 1)

    # Save to DB
    if not dry_run:
        save_to_db(result)
        print("  Saved to etoile.db")

    # Telegram notification
    tg_lines = [
        f"<b>LinkedIn Content</b> <code>{datetime.now().strftime('%H:%M')}</code>",
        f"Theme: {result['theme']}",
        f"Hashtags: {' '.join(result['hashtags'][:5])}",
        f"Post FR: {len(result['post_fr'])} chars",
        f"Post EN: {len(result['post_en'])} chars",
        f"Comments: {len(result['comments'])}",
        f"Agents: {', '.join(result['agents_used'])}",
        f"Time: {result['generation_time_s']}s",
    ]
    if not dry_run:
        send_telegram("\n".join(tg_lines))
        print("  Telegram sent")

    return result


def display_result(result):
    """Pretty-print the generated content."""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  LINKEDIN CONTENT — {result.get('theme', '?')}")
    print(f"  Generated in {result.get('generation_time_s', 0)}s")
    print(f"  Agents: {', '.join(result.get('agents_used', []))}")
    print(f"  Best posting time: {result.get('best_posting_time', '?')}")
    print(f"  Hashtags: {' '.join(result.get('hashtags', []))}")
    print(sep)

    print(f"\n--- POST FR ({len(result.get('post_fr', ''))} chars) ---\n")
    print(result.get("post_fr", "[none]"))

    print(f"\n--- POST EN ({len(result.get('post_en', ''))} chars) ---\n")
    print(result.get("post_en", "[none]"))

    print(f"\n--- COMMENTAIRES STRATEGIQUES ---\n")
    for i, c in enumerate(result.get("comments", []), 1):
        angle = c.get("angle", "?")
        text = c.get("text", "?")
        print(f"  [{i}] ({angle})")
        print(f"  {text}\n")

    print(sep)


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Content Generator — Cluster AI Pipeline")
    parser.add_argument("--idea", type=str, help="Raw idea for the post")
    parser.add_argument("--topic", type=str, default="tech/IA",
                        help="Target sector (default: tech/IA)")
    parser.add_argument("--tone", type=str, default="expert",
                        choices=["expert", "inspiring", "provocateur"],
                        help="Writing tone (default: expert)")
    parser.add_argument("--once", action="store_true",
                        help="Single generation (for orchestrator)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show prompts without calling agents")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of pretty-print")
    args = parser.parse_args()

    if not args.idea and not args.once:
        parser.print_help()
        print("\nExemple:")
        print('  python linkedin_content_generator.py --idea "Comment JARVIS '
              'automatise un cluster de 10 GPU" --topic "IA/DevOps"')
        sys.exit(1)

    # For --once without idea, use a default idea from recent activity
    idea = args.idea or "Les systemes IA distribues multi-GPU changent la donne pour les PME tech"

    result = generate_content(idea, args.topic, args.tone, args.dry_run)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        display_result(result)


if __name__ == "__main__":
    main()
