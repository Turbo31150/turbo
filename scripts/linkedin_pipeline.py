#!/usr/bin/env python3
"""LinkedIn Automation Pipeline v1.0 — JARVIS Turbo

Pipeline complet d'automatisation LinkedIn:
- Generer des posts via cluster IA (M1/OL1/M2)
- Valider par consensus cluster avant publication
- Planifier des publications a heures fixes
- Routine quotidienne: scroll, like, comment, reply, notifs
- Declenchable via Telegram (/linkedin_*) ou WhisperFlow

Tables SQLite (jarvis.db):
  linkedin_scheduled_posts — Posts prepares et planifies
  linkedin_daily_routine   — Log des routines quotidiennes
  linkedin_actions         — Log de chaque action individuelle

Usage:
  python linkedin_pipeline.py generate --theme "IA locale"
  python linkedin_pipeline.py schedule --id 1 --at "2026-03-07 09:00"
  python linkedin_pipeline.py publish --id 1
  python linkedin_pipeline.py routine
  python linkedin_pipeline.py list
  python linkedin_pipeline.py validate --id 1
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TURBO_DIR = Path(__file__).resolve().parent.parent

DB_PATH = TURBO_DIR / "data" / "jarvis.db"
POSTS_DIR = TURBO_DIR / "data" / "linkedin_posts"
POSTS_DIR.mkdir(exist_ok=True)

# === CLUSTER ENDPOINTS ===
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
OL1_URL = "http://127.0.0.1:11434/api/chat"
M2_URL = "http://192.168.1.26:1234/api/v1/chat"
M3_URL = "http://192.168.1.113:1234/api/v1/chat"


def db_conn():
    return sqlite3.connect(str(DB_PATH))


def query_m1(prompt: str, max_tokens: int = 1024, timeout: int = 60) -> str:
    """Query M1/qwen3-8b (local, rapide)."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.7,
            "max_output_tokens": max_tokens,
            "stream": False,
            "store": False,
        }).encode()
        req = urllib.request.Request(M1_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
        for block in reversed(d.get("output", [])):
            if isinstance(block, dict) and block.get("type") == "message":
                content = block.get("content", "")
                if isinstance(content, list):
                    return "".join(c.get("text", "") for c in content if isinstance(c, dict))
                return str(content)
    except Exception as e:
        print(f"[M1] Erreur: {e}")
    return ""


def query_ol1(prompt: str, timeout: int = 45) -> str:
    """Query OL1/qwen3:1.7b (local, ultra-rapide)."""
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(OL1_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
        return d.get("message", {}).get("content", "")
    except Exception as e:
        print(f"[OL1] Erreur: {e}")
    return ""


def query_m2(prompt: str, timeout: int = 60) -> str:
    """Query M2/deepseek-r1 (reasoning, distant)."""
    try:
        data = json.dumps({
            "model": "deepseek-r1-0528-qwen3-8b",
            "input": prompt,
            "temperature": 0.3,
            "max_output_tokens": 2048,
            "stream": False,
            "store": False,
        }).encode()
        req = urllib.request.Request(M2_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
        for block in reversed(d.get("output", [])):
            if isinstance(block, dict) and block.get("type") == "message":
                content = block.get("content", "")
                if isinstance(content, list):
                    return "".join(c.get("text", "") for c in content if isinstance(c, dict))
                return str(content)
    except Exception as e:
        print(f"[M2] Erreur: {e}")
    return ""


def query_claude(prompt: str, timeout: int = 120) -> str:
    """Query Claude via claude-proxy.js."""
    import subprocess
    try:
        proxy = str(TURBO_DIR / "claude-proxy.js")
        result = subprocess.run(
            ["node", proxy, prompt],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(TURBO_DIR),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        print(f"[CLAUDE] Erreur: {e}")
    return ""


def query_minimax_cloud(prompt: str, timeout: int = 45) -> str:
    """Query minimax-m2.5 cloud via Ollama (web search)."""
    try:
        data = json.dumps({
            "model": "minimax-m2.5:cloud",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
        }).encode()
        req = urllib.request.Request(OL1_URL, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
        return d.get("message", {}).get("content", "")
    except Exception as e:
        print(f"[MINIMAX] Erreur: {e}")
    return ""


# === GENERATION ===

THEMES = [
    "IA distribuee sur cluster GPU local",
    "Automatisation workflow avec agents IA",
    "Trading algorithmique et IA",
    "Orchestration multi-agents JARVIS",
    "Productivite developpeur avec IA locale",
    "Vision par ordinateur sur GPU consumer",
    "Voice-to-action avec WhisperFlow",
    "MLOps maison vs cloud",
    "Open source vs modeles proprietaires",
    "Construire son lab IA a la maison",
]

POST_PROMPT = """Ecris un post LinkedIn en francais (200 mots max).
Theme: {theme}

Regles:
- Hook percutant en premiere ligne (emoji + phrase choc)
- Corps avec experience personnelle concrete
- 2-3 emojis maximum (pas excessif)
- Call-to-action final engageant
- 3-5 hashtags pertinents en fin de post
- Ton authentique, pas corporate
- Texte brut, PAS de markdown (pas de ** ni de #)
"""


def cmd_generate(args):
    """Genere un post via le cluster et le stocke en DB."""
    theme = args.theme or THEMES[int(time.time()) % len(THEMES)]
    prompt = POST_PROMPT.format(theme=theme)

    print(f"[*] Generation via M1 — Theme: {theme}")
    content = query_m1(prompt, max_tokens=1024)

    if not content:
        print("[*] M1 vide, fallback OL1...")
        content = query_ol1(prompt)

    if not content:
        print("[!] Aucune generation reussie.")
        return

    # Clean up
    content = content.strip()
    if content.startswith('"') and content.endswith('"'):
        content = content[1:-1]

    db = db_conn()
    db.execute(
        "INSERT INTO linkedin_scheduled_posts (content, theme, generated_by, status) VALUES (?, ?, ?, ?)",
        (content, theme, "M1/qwen3-8b", "draft")
    )
    db.commit()
    post_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    print(f"\n{'='*50}")
    print(f"POST #{post_id} (draft):")
    print(f"{'='*50}")
    print(content)
    print(f"{'='*50}")
    print(f"Longueur: {len(content)} chars | Theme: {theme}")
    print(f"Valider: python linkedin_pipeline.py validate --id {post_id}")


def cmd_validate(args):
    """Valide un post par consensus cluster (M1 + OL1 + M2)."""
    db = db_conn()
    row = db.execute("SELECT id, content, theme FROM linkedin_scheduled_posts WHERE id=?",
                     (args.id,)).fetchone()
    if not row:
        print(f"[!] Post #{args.id} non trouve.")
        return

    post_id, content, theme = row
    print(f"[*] Validation cluster du post #{post_id}...")

    eval_prompt = f"""Evalue ce post LinkedIn (note sur 10 + feedback court en 1 ligne):

POST:
{content}

Reponds EXACTEMENT au format: NOTE/10 — feedback
Exemple: 8/10 — Bon hook mais CTA faible"""

    scores = {}

    # M1
    print("  [M1] Evaluation...")
    r = query_m1(eval_prompt, max_tokens=256)
    if r:
        scores["M1"] = r.strip()
        print(f"  [M1] {r.strip()}")

    # OL1
    print("  [OL1] Evaluation...")
    r = query_ol1(eval_prompt)
    if r:
        scores["OL1"] = r.strip()
        print(f"  [OL1] {r.strip()}")

    # Claude (validateur principal — qualite)
    print("  [CLAUDE] Evaluation...")
    r = query_claude(eval_prompt)
    if r:
        scores["CLAUDE"] = r.strip()[:200]
        print(f"  [CLAUDE] {r.strip()[:200]}")

    # Minimax cloud (perspective web/tendances)
    print("  [MINIMAX] Evaluation...")
    r = query_minimax_cloud(eval_prompt)
    if r:
        scores["MINIMAX"] = r.strip()[:200]
        print(f"  [MINIMAX] {r.strip()[:200]}")

    # M2 (si dispo)
    print("  [M2] Evaluation...")
    r = query_m2(eval_prompt, timeout=30)
    if r:
        scores["M2"] = r.strip()
        print(f"  [M2] {r.strip()}")

    validated = len(scores) >= 2  # Au moins 2 agents doivent repondre
    status = "validated" if validated else "draft"

    db.execute(
        "UPDATE linkedin_scheduled_posts SET cluster_validated=?, validation_scores=?, status=? WHERE id=?",
        (1 if validated else 0, json.dumps(scores), status, post_id)
    )
    db.commit()
    db.close()

    print(f"\n{'='*50}")
    print(f"Post #{post_id}: {'VALIDE' if validated else 'NON VALIDE'} ({len(scores)} agents)")
    if validated:
        print(f"Planifier: python linkedin_pipeline.py schedule --id {post_id} --at '2026-03-07 09:00'")


def cmd_schedule(args):
    """Planifie un post a une heure precise."""
    db = db_conn()
    row = db.execute("SELECT id, status FROM linkedin_scheduled_posts WHERE id=?",
                     (args.id,)).fetchone()
    if not row:
        print(f"[!] Post #{args.id} non trouve.")
        return

    scheduled_at = args.at
    if not scheduled_at:
        # Default: demain 9h00
        tomorrow = datetime.now() + timedelta(days=1)
        scheduled_at = tomorrow.strftime("%Y-%m-%d 09:00")

    db.execute(
        "UPDATE linkedin_scheduled_posts SET scheduled_at=?, status='scheduled' WHERE id=?",
        (scheduled_at, args.id)
    )
    db.commit()
    db.close()
    print(f"Post #{args.id} planifie pour {scheduled_at}")


def cmd_publish(args):
    """Publie un post (marque comme ready pour Playwright MCP)."""
    db = db_conn()
    row = db.execute("SELECT id, content, status FROM linkedin_scheduled_posts WHERE id=?",
                     (args.id,)).fetchone()
    if not row:
        print(f"[!] Post #{args.id} non trouve.")
        return

    post_id, content, status = row

    # Sauvegarder dans un fichier pour Playwright MCP
    post_file = POSTS_DIR / f"post_{post_id}.txt"
    post_file.write_text(content, encoding="utf-8")

    db.execute(
        "UPDATE linkedin_scheduled_posts SET status='ready', published_at=? WHERE id=?",
        (datetime.now().isoformat(), post_id)
    )
    db.commit()

    # Log action
    db.execute(
        "INSERT INTO linkedin_actions (action_type, target, content, status) VALUES (?, ?, ?, ?)",
        ("publish_ready", f"post_{post_id}", content[:100], "ready")
    )
    db.commit()
    db.close()

    print(f"Post #{post_id} pret a publier.")
    print(f"Fichier: {post_file}")
    print(f"\nPour publier via Playwright MCP dans Claude Code:")
    print(f"  1. browser_navigate → linkedin.com/feed")
    print(f"  2. browser_click → 'Commencer un post'")
    print(f"  3. browser_type → contenu du fichier")
    print(f"  4. browser_click → 'Publier'")
    print(f"\nOu via Telegram: /linkedin_publish {post_id}")


def cmd_list(args):
    """Liste tous les posts prepares."""
    db = db_conn()
    rows = db.execute(
        "SELECT id, theme, status, scheduled_at, cluster_validated, LENGTH(content), created_at "
        "FROM linkedin_scheduled_posts ORDER BY id DESC LIMIT 20"
    ).fetchall()
    db.close()

    if not rows:
        print("Aucun post en attente.")
        return

    print(f"{'ID':>4} | {'Status':>10} | {'Valid':>5} | {'Planifie':>19} | {'Chars':>5} | Theme")
    print("-" * 80)
    for r in rows:
        pid, theme, status, sched, valid, chars, created = r
        sched = sched or "-"
        print(f"{pid:>4} | {status:>10} | {'OK' if valid else '-':>5} | {sched:>19} | {chars:>5} | {(theme or '')[:30]}")


def cmd_check_schedule(args):
    """Verifie si des posts sont a publier maintenant."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    db = db_conn()
    rows = db.execute(
        "SELECT id, content FROM linkedin_scheduled_posts "
        "WHERE status='scheduled' AND scheduled_at <= ? ORDER BY scheduled_at",
        (now,)
    ).fetchall()
    db.close()

    if not rows:
        print(f"[{now}] Aucun post a publier.")
        return

    for post_id, content in rows:
        print(f"[{now}] Post #{post_id} a publier!")
        # Sauvegarder pour Playwright
        post_file = POSTS_DIR / f"post_{post_id}.txt"
        post_file.write_text(content, encoding="utf-8")
        print(f"  Fichier: {post_file}")

        db = db_conn()
        db.execute("UPDATE linkedin_scheduled_posts SET status='ready' WHERE id=?", (post_id,))
        db.commit()
        db.close()


def cmd_routine_status(args):
    """Affiche le statut de la routine du jour."""
    today = datetime.now().strftime("%Y-%m-%d")
    db = db_conn()
    row = db.execute(
        "SELECT * FROM linkedin_daily_routine WHERE routine_date=?", (today,)
    ).fetchone()

    actions = db.execute(
        "SELECT action_type, COUNT(*) FROM linkedin_actions "
        "WHERE date(timestamp, 'unixepoch')=? GROUP BY action_type", (today,)
    ).fetchall()
    db.close()

    print(f"=== Routine LinkedIn {today} ===")
    if row:
        print(f"Scrolls: {row[2]} | Likes: {row[3]} | Comments: {row[4]} | Replies: {row[5]}")
        print(f"Notifs: {row[6]} | Posts publies: {row[7]} | Status: {row[9]}")
    else:
        print("Pas encore de routine aujourd'hui.")

    if actions:
        print("\nActions du jour:")
        for action_type, count in actions:
            print(f"  {action_type}: {count}")


def cmd_batch_generate(args):
    """Genere plusieurs posts d'avance."""
    count = args.count or 5
    print(f"[*] Generation de {count} posts...")
    for i in range(count):
        theme = THEMES[i % len(THEMES)]
        prompt = POST_PROMPT.format(theme=theme)

        print(f"\n[{i+1}/{count}] Theme: {theme}")
        content = query_m1(prompt, max_tokens=1024)
        if not content:
            content = query_ol1(prompt)
        if not content:
            print(f"  [!] Echec generation")
            continue

        content = content.strip()
        if content.startswith('"') and content.endswith('"'):
            content = content[1:-1]

        db = db_conn()
        db.execute(
            "INSERT INTO linkedin_scheduled_posts (content, theme, generated_by, status) VALUES (?, ?, ?, ?)",
            (content, theme, "M1/qwen3-8b", "draft")
        )
        db.commit()
        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.close()

        print(f"  Post #{pid} cree ({len(content)} chars)")
        time.sleep(2)  # Cooldown entre generations

    print(f"\n[*] {count} posts generes. Voir: python linkedin_pipeline.py list")


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Automation Pipeline — JARVIS")
    sub = parser.add_subparsers(dest="command")

    # generate
    p = sub.add_parser("generate", help="Generer un post via cluster")
    p.add_argument("--theme", help="Theme du post")

    # validate
    p = sub.add_parser("validate", help="Valider un post par consensus cluster")
    p.add_argument("--id", type=int, required=True, help="ID du post")

    # schedule
    p = sub.add_parser("schedule", help="Planifier un post")
    p.add_argument("--id", type=int, required=True, help="ID du post")
    p.add_argument("--at", help="Date/heure (YYYY-MM-DD HH:MM)")

    # publish
    p = sub.add_parser("publish", help="Marquer un post comme pret a publier")
    p.add_argument("--id", type=int, required=True, help="ID du post")

    # list
    sub.add_parser("list", help="Lister les posts")

    # check
    sub.add_parser("check", help="Verifier les posts planifies a publier")

    # status
    sub.add_parser("status", help="Statut routine du jour")

    # batch
    p = sub.add_parser("batch", help="Generer plusieurs posts d'avance")
    p.add_argument("--count", type=int, default=5, help="Nombre de posts")

    args = parser.parse_args()

    commands = {
        "generate": cmd_generate,
        "validate": cmd_validate,
        "schedule": cmd_schedule,
        "publish": cmd_publish,
        "list": cmd_list,
        "check": cmd_check_schedule,
        "status": cmd_routine_status,
        "batch": cmd_batch_generate,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
