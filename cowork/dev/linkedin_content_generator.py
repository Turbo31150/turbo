#!/usr/bin/env python3
"""LinkedIn post generator via local AI cluster + BrowserOS MCP publish.
Usage: --once (generate+publish) | --generate (no publish) | --topic TOPIC
"""
import argparse, json, sqlite3, sys, time, urllib.request
from datetime import datetime

M1_URL, M1_MODEL = "http://127.0.0.1:1234/api/v1/chat", "qwen3-8b"
BROWSEROS_URL = "http://127.0.0.1:9000/mcp"
ETOILE_DB, LINKEDIN_URL = "F:/BUREAU/turbo/etoile.db", "https://www.linkedin.com/feed/"
DEFAULT_TOPIC = "JARVIS: infrastructure IA distribuee multi-GPU, orchestration automatique de cluster local avec agents autonomes"
PROMPT = """/nothink
Tu es un expert LinkedIn tech/IA avec 50K followers. Genere un post LinkedIn engageant.
SUJET: {topic}
Reponds en JSON strict (pas de markdown):
{{"title": "titre accrocheur (1 ligne)", "body": "texte du post (max 2500 chars, sauts de ligne, storytelling, CTA en fin)", "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"], "emoji": "1 emoji pertinent"}}"""

def call_m1(prompt, timeout=60):
    body = json.dumps({"model": M1_MODEL, "input": prompt, "temperature": 0.4,
                        "max_output_tokens": 2048, "stream": False, "store": False}).encode()
    req = urllib.request.Request(M1_URL, body, {"Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    for block in reversed(data.get("output", [])):
        if block.get("type") == "message":
            for c in block.get("content", []):
                if c.get("type") == "output_text":
                    return c.get("text", "")
    return ""

def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```"))
    start, end = text.find("{"), text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None

def browseros_call(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": method, "arguments": params}}).encode()
    req = urllib.request.Request(BROWSEROS_URL, body, {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def publish_to_linkedin(post):
    print("[PUBLISH] Opening LinkedIn...", flush=True)
    browseros_call("new_page", {"url": LINKEDIN_URL})
    time.sleep(3)
    browseros_call("click", {"selector": "button.share-box-feed-entry__trigger"})
    time.sleep(2)
    full_text = f"{post['emoji']} {post['title']}\n\n{post['body']}\n\n{' '.join(post['hashtags'])}"
    browseros_call("fill", {"selector": "div.ql-editor", "value": full_text})
    print("[PUBLISH] Post filled. Review and click 'Post' manually.")

def log_to_db(post):
    db = sqlite3.connect(ETOILE_DB, timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("INSERT OR REPLACE INTO memories (category, key, value, source, confidence) VALUES (?, ?, ?, ?, ?)",
               ("linkedin_post", f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                json.dumps(post, ensure_ascii=False), "linkedin_content_generator", 1.0))
    db.commit()
    db.close()

def generate(topic):
    print(f"[GEN] Topic: {topic}", flush=True)
    t0 = time.time()
    raw = call_m1(PROMPT.format(topic=topic))
    post = parse_json(raw)
    if not post or "body" not in post:
        print("[WARN] M1 returned unparseable response, using raw text", file=sys.stderr)
        post = {"title": topic[:80], "body": raw[:2500], "hashtags": ["#IA", "#Tech", "#JARVIS"], "emoji": "\U0001f680"}
    post["generated_at"] = datetime.now().isoformat()
    post["generation_time_s"] = round(time.time() - t0, 1)
    post["agent"] = "M1/qwen3-8b"
    print(f"[GEN] Done in {post['generation_time_s']}s ({len(post['body'])} chars)")
    return post

def main():
    ap = argparse.ArgumentParser(description="LinkedIn post generator via local AI cluster")
    ap.add_argument("--once", action="store_true", help="Generate 1 post and publish via BrowserOS")
    ap.add_argument("--generate", action="store_true", help="Generate without publishing")
    ap.add_argument("--topic", type=str, default=None, help="Specific topic")
    args = ap.parse_args()
    if not args.once and not args.generate:
        ap.print_help()
        sys.exit(1)
    post = generate(args.topic or DEFAULT_TOPIC)
    try:
        log_to_db(post)
        print("[DB] Saved to etoile.db")
    except Exception as e:
        print(f"[DB] Error: {e}", file=sys.stderr)
    if args.once:
        try:
            publish_to_linkedin(post)
        except Exception as e:
            print(f"[PUBLISH] Error: {e}", file=sys.stderr)
    print(json.dumps(post, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
