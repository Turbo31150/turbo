#!/usr/bin/env python3
"""LinkedIn Growth Engine — Automated growth loop orchestrator.

Orchestrates the full LinkedIn growth cycle:
  Phase 1: Research (Perplexity/minimax web search)
  Phase 2: Content (M1/M2 cluster + external AI prompts)
  Phase 3: Engagement (profile visits, comments, scheduling)
  Phase 4: Analytics (tracking, scoring, iteration)

Designed to be run as:
  - Manual: python linkedin_growth_engine.py --full-cycle
  - Scheduled: via JARVIS TaskScheduler (daily/weekly)
  - Telegram: /linkedin command
  - Domino: voice trigger "lance la boucle linkedin"

Stdlib-only. Uses existing linkedin_content_generator.py for content generation.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT, TURBO_DIR

# ═══════════════════════════════════════════════════════════════════════════
# PROMPTS BANK — Ready-to-use for external AI (Perplexity, ChatGPT, Claude)
# ═══════════════════════════════════════════════════════════════════════════

PROMPTS = {
    # --- PERPLEXITY (web research) ---
    "perplexity_trends": """Quelles sont les 5 tendances LinkedIn les plus engageantes cette semaine dans le secteur {sector}?
Pour chaque tendance:
- Sujet exact
- Pourquoi ca engage (donnees si possible)
- Un angle de post original
- 3 hashtags pertinents
Focus: France + international. Donnees < 7 jours.""",

    "perplexity_competitors": """Analyse les 10 meilleurs createurs LinkedIn dans le secteur "{sector}" en France.
Pour chacun:
- Nom et URL profil
- Frequence de publication
- Type de contenu qui marche le mieux (carousel, texte, video)
- Taux d'engagement moyen
- Leur hook le plus viral
Je veux m'en inspirer sans copier. Donne des patterns replicables.""",

    "perplexity_hooks": """Donne-moi 20 hooks LinkedIn qui ont genere plus de 1000 likes dans le secteur {sector}.
Format: le hook exact, suivi du pattern sous-jacent.
Exemples de patterns: curiosity gap, contrarian take, personal story, data shock, before/after.
Je veux des hooks FR ET EN.""",

    # --- CHATGPT (creative content) ---
    "chatgpt_post_fr": """Tu es un ghostwriter LinkedIn premium avec 100K followers.

BRIEF:
- Sujet: {topic}
- Angle: {angle}
- Ton: {tone}
- Audience cible: {audience}
- Objectif: {goal}

STRUCTURE OBLIGATOIRE:
1. HOOK (1 ligne) — arrete le scroll, cree un gap de curiosite
2. CONTEXTE (2-3 lignes) — pose le probleme ou la situation
3. CORPS (5-8 lignes) — insight principal avec donnees/experience
4. TWIST (1-2 lignes) — retournement ou insight contre-intuitif
5. CTA (1 ligne) — question ou call-to-action qui invite au commentaire

REGLES:
- Max 1300 caracteres (sweet spot LinkedIn)
- Sauts de ligne apres chaque phrase
- Zero emoji sauf si strategique (1 max)
- Pas de hashtags dans le corps (les ajouter apres)
- Texte brut, zero markdown
- Parle a la premiere personne (je/nous)""",

    "chatgpt_post_en": """You are a premium LinkedIn ghostwriter (100K+ followers).

BRIEF:
- Topic: {topic}
- Angle: {angle}
- Tone: {tone}
- Target: {audience}
- Goal: {goal}

ADAPT this French post to native English LinkedIn style:
{post_fr}

RULES:
- Not a translation — a native English adaptation
- Keep the hook impact, adjust cultural references
- Same structure: Hook → Context → Body → Twist → CTA
- Max 1300 chars
- Line breaks between each sentence
- Plain text, no markdown, no emojis (1 max if strategic)""",

    "chatgpt_comments": """Generate 5 strategic LinkedIn comments for someone who is an expert in {sector}.

Each comment will be posted on other people's posts to gain visibility.
The goal is to ADD VALUE, not to self-promote.

For each comment provide:
1. Target post type (what kind of post to comment on)
2. The comment (80-150 words)
3. The strategic angle (experience sharing / data addition / thoughtful question / contrarian view / practical tip)

Mix of French AND English comments (3 FR, 2 EN).
Tone: confident expert, conversational, specific (no generic "great post!").""",

    # --- CLAUDE/OPENCLAW (strategy + quality review) ---
    "claude_strategy": """Analyse cette strategie de growth LinkedIn et donne un score /100 + recommandations:

PROFIL: {profile_summary}
POSTS RECENTS (dernieres 2 semaines):
{recent_posts}

METRIQUES:
- Posts par semaine: {posts_per_week}
- Engagement moyen: {avg_engagement}
- Croissance followers: {follower_growth}

Evaluate:
1. Consistance editoriale (sur 20)
2. Qualite des hooks (sur 20)
3. Engagement CTA (sur 20)
4. Diversite formats (sur 20)
5. Positionnement unique (sur 20)

Pour chaque critere: score + 1 action concrete a faire cette semaine.""",

    "claude_review_post": """Revois ce post LinkedIn et donne:
1. Score /100 (engagement predit)
2. 3 forces
3. 3 faiblesses
4. Version amelioree du hook (2 alternatives)
5. CTA optimise

POST:
{post_text}

Sois brutal mais constructif. L'objectif: >2% engagement rate.""",

    # --- M1/CLUSTER (fast tasks) ---
    "m1_hashtags": """/nothink
Genere 10 hashtags LinkedIn optimises pour ce post.
5 populaires (>10K posts) + 5 niche (<5K posts mais ultra-cibles).
Reponds UNIQUEMENT en JSON: {{"popular": ["#h1",...], "niche": ["#h1",...]}}

Post: {post_summary}
Secteur: {sector}""",

    "m1_schedule": """/nothink
Quel est le meilleur moment pour poster sur LinkedIn cette semaine?
Audience cible: {audience}
Timezone: Europe/Paris
Jour actuel: {day}

Reponds en JSON: {{"best_day": "...", "best_time": "HH:MM", "reason": "...", "alternatives": ["jour HH:MM", ...]}}""",
}


# ═══════════════════════════════════════════════════════════════════════════
# AGENT HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def call_m1(prompt, timeout=30):
    """Quick call to M1 (qwen3-8b, local, fast)."""
    try:
        body = json.dumps({
            "model": "qwen3-8b",
            "input": prompt,
            "temperature": 0.3,
            "max_output_tokens": 2048,
            "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat", body,
            {"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        for block in reversed(data.get("output", [])):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "")
        return str(data.get("output", ""))
    except Exception as e:
        return f"[M1 error: {e}]"


def call_minimax_web(prompt, timeout=60):
    """Web search via minimax-m2.5 cloud (Ollama)."""
    try:
        body = json.dumps({
            "model": "minimax-m2.5:cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat", body,
            {"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        return data.get("message", {}).get("content", "")
    except Exception as e:
        return f"[minimax error: {e}]"


def send_telegram(text, parse_mode="HTML"):
    """Send Telegram notification."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT,
        "text": text[:4000],
        "parse_mode": parse_mode,
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def parse_json_safe(text):
    """Extract JSON from text that may have markdown fences."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# GROWTH PHASES
# ═══════════════════════════════════════════════════════════════════════════

def phase_research(sector, output_dir):
    """Phase 1: Research trends + competitors via web search."""
    print("\n[PHASE 1] RESEARCH — Tendances et veille concurrentielle")
    results = {}

    # Trends via minimax (web search)
    print("  Recherche tendances...")
    prompt = PROMPTS["perplexity_trends"].format(sector=sector)
    trends = call_minimax_web(prompt)
    results["trends"] = trends
    print(f"  Trends: {len(trends)} chars")

    # Hooks inspirations
    print("  Recherche hooks viraux...")
    prompt = PROMPTS["perplexity_hooks"].format(sector=sector)
    hooks = call_minimax_web(prompt)
    results["hooks"] = hooks
    print(f"  Hooks: {len(hooks)} chars")

    # Save research
    research_file = output_dir / f"research_{datetime.now().strftime('%Y%m%d')}.json"
    with open(research_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {research_file}")

    return results


def phase_content(sector, idea, tone, research=None):
    """Phase 2: Generate content using existing pipeline."""
    print("\n[PHASE 2] CONTENT — Generation de contenu")

    # Use existing generator
    from linkedin_content_generator import generate_content
    result = generate_content(idea, sector, tone)

    # Generate external AI prompts for manual quality boost
    prompts_ready = {
        "chatgpt_post_fr": PROMPTS["chatgpt_post_fr"].format(
            topic=result.get("theme", sector),
            angle="expertise + experience concrete",
            tone=tone,
            audience=result.get("target_audience", "pros tech"),
            goal="generer des commentaires qualifies",
        ),
        "chatgpt_comments": PROMPTS["chatgpt_comments"].format(sector=sector),
        "claude_review": PROMPTS["claude_review_post"].format(
            post_text=result.get("post_fr", "")[:2000],
        ),
    }
    result["external_prompts"] = prompts_ready

    return result


def phase_scheduling(content_result):
    """Phase 3: Determine optimal posting time."""
    print("\n[PHASE 3] SCHEDULING — Planification optimale")

    day = datetime.now().strftime("%A")
    audience = content_result.get("target_audience", "professionnels tech")

    prompt = PROMPTS["m1_schedule"].format(audience=audience, day=day)
    raw = call_m1(prompt)
    schedule = parse_json_safe(raw) or {
        "best_day": "Mardi", "best_time": "08:30",
        "reason": "Pic activite LinkedIn matin", "alternatives": []
    }

    content_result["schedule"] = schedule
    print(f"  Best time: {schedule.get('best_day', '?')} {schedule.get('best_time', '08:30')}")
    print(f"  Reason: {schedule.get('reason', '?')}")

    return content_result


def phase_analytics(sector):
    """Phase 4: Track performance and generate insights."""
    print("\n[PHASE 4] ANALYTICS — Suivi des performances")

    db = sqlite3.connect(str(ETOILE_DB), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")

    try:
        # Count generated content
        total = db.execute("SELECT COUNT(*) FROM linkedin_content").fetchone()[0]
        recent = db.execute(
            "SELECT COUNT(*) FROM linkedin_content WHERE timestamp > datetime('now', '-7 days')"
        ).fetchone()[0]
        # Get agents distribution
        agents = db.execute(
            "SELECT agents_used, COUNT(*) FROM linkedin_content GROUP BY agents_used ORDER BY 2 DESC LIMIT 5"
        ).fetchall()

        stats = {
            "total_generated": total,
            "this_week": recent,
            "agent_distribution": {a: c for a, c in agents},
        }
        print(f"  Total posts generes: {total}")
        print(f"  Cette semaine: {recent}")
        return stats

    except sqlite3.OperationalError:
        print("  Table linkedin_content n'existe pas encore")
        return {"total_generated": 0, "this_week": 0}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
# FULL CYCLE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

def full_cycle(idea, sector="tech/IA", tone="expert"):
    """Execute the complete LinkedIn growth cycle."""
    t0 = time.time()
    sep = "=" * 60
    print(sep)
    print("  LINKEDIN GROWTH ENGINE — Full Cycle")
    print(f"  Sector: {sector} | Tone: {tone}")
    print(f"  Started: {datetime.now().strftime('%H:%M:%S')}")
    print(sep)

    output_dir = TURBO_DIR / "data" / "linkedin"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Research
    research = phase_research(sector, output_dir)

    # Phase 2: Content
    content = phase_content(sector, idea, tone, research)

    # Phase 3: Scheduling
    content = phase_scheduling(content)

    # Phase 4: Analytics
    analytics = phase_analytics(sector)

    # Summary
    elapsed = round(time.time() - t0, 1)
    print(f"\n{sep}")
    print(f"  CYCLE COMPLETE — {elapsed}s")
    print(sep)

    # Export prompts for external AI
    prompts_file = output_dir / f"prompts_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(prompts_file, "w", encoding="utf-8") as f:
        json.dump({
            "perplexity": {
                "trends": PROMPTS["perplexity_trends"].format(sector=sector),
                "competitors": PROMPTS["perplexity_competitors"].format(sector=sector),
            },
            "chatgpt": content.get("external_prompts", {}),
            "cluster_result": {
                "post_fr": content.get("post_fr", ""),
                "post_en": content.get("post_en", ""),
                "hashtags": content.get("hashtags", []),
                "comments": content.get("comments", []),
                "schedule": content.get("schedule", {}),
            },
            "analytics": analytics,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nPrompts exports: {prompts_file}")

    # Telegram summary
    tg = [
        "<b>LinkedIn Growth Cycle</b>",
        f"Theme: {content.get('theme', '?')}",
        f"Post FR: {len(content.get('post_fr', ''))} chars",
        f"Post EN: {len(content.get('post_en', ''))} chars",
        f"Comments: {len(content.get('comments', []))}",
        f"Schedule: {content.get('schedule', {}).get('best_day', '?')} {content.get('schedule', {}).get('best_time', '?')}",
        f"Prompts: {prompts_file.name}",
        f"Time: {elapsed}s",
    ]
    send_telegram("\n".join(tg))

    return content


def export_prompts_only(sector="tech/IA", topic="", audience="pros tech", tone="expert"):
    """Export only the prompt bank (no AI calls) for manual use."""
    output_dir = TURBO_DIR / "data" / "linkedin"
    output_dir.mkdir(parents=True, exist_ok=True)

    bank = {
        "perplexity": {
            "trends": PROMPTS["perplexity_trends"].format(sector=sector),
            "competitors": PROMPTS["perplexity_competitors"].format(sector=sector),
            "hooks": PROMPTS["perplexity_hooks"].format(sector=sector),
        },
        "chatgpt": {
            "post_fr": PROMPTS["chatgpt_post_fr"].format(
                topic=topic or sector, angle="expertise concrete",
                tone=tone, audience=audience, goal="engagement + followers"),
            "post_en": PROMPTS["chatgpt_post_en"].format(
                topic=topic or sector, angle="expertise",
                tone=tone, audience=audience, goal="engagement",
                post_fr="[COLLER LE POST FR ICI]"),
            "comments": PROMPTS["chatgpt_comments"].format(sector=sector),
        },
        "claude_openclaw": {
            "strategy_review": PROMPTS["claude_strategy"].format(
                profile_summary="[COLLER RESUME PROFIL]",
                recent_posts="[COLLER 3 DERNIERS POSTS]",
                posts_per_week="?", avg_engagement="?%",
                follower_growth="+?/semaine"),
            "post_review": PROMPTS["claude_review_post"].format(
                post_text="[COLLER LE POST A REVIEWER]"),
        },
    }

    out_file = output_dir / f"prompt_bank_{datetime.now().strftime('%Y%m%d')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)

    print(f"Prompt bank exported: {out_file}")
    print(f"\nCategories: {list(bank.keys())}")
    for cat, prompts in bank.items():
        print(f"  {cat}: {list(prompts.keys())}")

    return bank, out_file


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Growth Engine")
    parser.add_argument("--full-cycle", action="store_true",
                        help="Run complete growth cycle")
    parser.add_argument("--prompts-only", action="store_true",
                        help="Export prompt bank only (no AI calls)")
    parser.add_argument("--research", action="store_true",
                        help="Research phase only (web search)")
    parser.add_argument("--analytics", action="store_true",
                        help="Analytics phase only")
    parser.add_argument("--idea", type=str,
                        default="Les systemes IA distribues multi-GPU changent la donne")
    parser.add_argument("--sector", type=str, default="tech/IA")
    parser.add_argument("--tone", type=str, default="expert",
                        choices=["expert", "inspiring", "provocateur"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.prompts_only:
        bank, path = export_prompts_only(args.sector, args.idea, tone=args.tone)
        if args.json:
            print(json.dumps(bank, indent=2, ensure_ascii=False))
        return

    if args.research:
        output_dir = TURBO_DIR / "data" / "linkedin"
        output_dir.mkdir(parents=True, exist_ok=True)
        research = phase_research(args.sector, output_dir)
        if args.json:
            print(json.dumps(research, indent=2, ensure_ascii=False))
        return

    if args.analytics:
        stats = phase_analytics(args.sector)
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    if args.full_cycle:
        result = full_cycle(args.idea, args.sector, args.tone)
        if args.json:
            # Remove non-serializable
            safe = {k: v for k, v in result.items()
                    if isinstance(v, (str, int, float, list, dict, bool, type(None)))}
            print(json.dumps(safe, indent=2, ensure_ascii=False))
        return

    parser.print_help()
    print("\nExemples:")
    print("  python linkedin_growth_engine.py --prompts-only --sector 'IA/automation'")
    print("  python linkedin_growth_engine.py --full-cycle --idea 'JARVIS automatise tout'")
    print("  python linkedin_growth_engine.py --research --sector 'SaaS/B2B'")


if __name__ == "__main__":
    main()
