#!/usr/bin/env python3
"""ChatGPT Dispatcher — Send tasks to ChatGPT via Comet browser CDP (port 9222).

stdlib-only, argparse --once, JSON output.
Modes: --query, --research, --compare (ChatGPT vs M1), --batch FILE.
"""
import argparse, json, time, sqlite3, os, sys
import urllib.request, urllib.error
from datetime import datetime

CDP_URL = "http://127.0.0.1:9222"
CHATGPT_PATTERNS = ["chatgpt", "chat.openai"]
M1_URL = "http://127.0.0.1:1234/api/v1/chat"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "etoile.db")
POLL_INTERVAL = 2
POLL_TIMEOUT = 60


def _req(url, data=None, timeout=10):
    """HTTP request helper, returns parsed JSON or None."""
    try:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        body = json.dumps(data).encode() if data else None
        with urllib.request.urlopen(req, body, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _cdp_send(ws_url, method, params=None):
    """Minimal CDP via HTTP debug endpoint — uses Runtime.evaluate through /json/protocol.
    Falls back to a simple evaluate via the page's /json endpoint."""
    # We use the REST debug API instead of raw WebSocket for stdlib-only
    pass


def _find_chatgpt_page():
    """Find an existing ChatGPT tab or open one. Returns page dict or None."""
    pages = _req(f"{CDP_URL}/json")
    if pages:
        for p in pages:
            url = p.get("url", "")
            if any(pat in url for pat in CHATGPT_PATTERNS):
                return p
    # No page found — open one
    new = _req(f"{CDP_URL}/json/new?https://chat.openai.com")
    if new:
        time.sleep(4)
        return new
    return None


def _cdp_eval(page, expr):
    """Evaluate JS on page via CDP REST protocol (devtools HTTP)."""
    ws = page.get("webSocketDebuggerUrl", "")
    page_id = ws.split("/")[-1] if ws else page.get("id", "")
    url = f"{CDP_URL}/json/protocol"  # not used directly
    # Use the /json endpoint approach — send via fetch to devtools
    # Actually use the page's devtools URL for evaluation
    eval_url = f"{CDP_URL}/json"
    # CDP HTTP doesn't support eval directly; use a small trick:
    # We POST to the page's ws via a minimal CDP message over HTTP
    # Fallback: use the /json/evaluate endpoint if available, else return None
    try:
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", 9222, timeout=15)
        # Send CDP command via HTTP POST to /json/command
        # This is not standard; we use websocket-less approach
        # Real approach: use a minimal websocket handshake
        conn.close()
    except Exception:
        pass
    return None


def send_to_chatgpt(query):
    """Send query to ChatGPT via CDP. Returns answer or None."""
    page = _find_chatgpt_page()
    if not page:
        return None
    ws_url = page.get("webSocketDebuggerUrl")
    if not ws_url:
        return None

    # Build JS to inject query and click send
    js_fill = f"""
    (function() {{
        let ta = document.querySelector('textarea#prompt-textarea') || document.querySelector('div#prompt-textarea');
        if (!ta) return 'NO_TEXTAREA';
        if (ta.tagName === 'TEXTAREA') {{ ta.value = {json.dumps(query)}; }}
        else {{ ta.textContent = {json.dumps(query)}; }}
        ta.dispatchEvent(new Event('input', {{bubbles: true}}));
        return 'FILLED';
    }})()
    """
    js_click = """
    (function() {
        let btn = document.querySelector('button[data-testid="send-button"]')
            || document.querySelector('button[aria-label="Send"]')
            || document.querySelector('form button[type="submit"]');
        if (!btn) return 'NO_BUTTON';
        btn.click();
        return 'CLICKED';
    })()
    """
    js_read = """
    (function() {
        let msgs = document.querySelectorAll('div[data-message-author-role="assistant"]');
        if (!msgs.length) return '';
        let last = msgs[msgs.length - 1];
        return last.textContent || '';
    })()
    """
    # Since stdlib has no WebSocket, we attempt via a subprocess call to node
    try:
        import subprocess
        script = f"""
        const WebSocket = require('ws');
        const ws = new WebSocket('{ws_url}');
        let id = 1;
        function send(method, params) {{
            return new Promise(r => {{
                const mid = id++;
                ws.send(JSON.stringify({{id: mid, method, params}}));
                ws.once('message', m => r(JSON.parse(m)));
            }});
        }}
        ws.on('open', async () => {{
            await send('Runtime.evaluate', {{expression: {json.dumps(js_fill)}}});
            await new Promise(r => setTimeout(r, 500));
            await send('Runtime.evaluate', {{expression: {json.dumps(js_click)}}});
            let answer = '';
            for (let i = 0; i < {POLL_TIMEOUT // POLL_INTERVAL}; i++) {{
                await new Promise(r => setTimeout(r, {POLL_INTERVAL * 1000}));
                const res = await send('Runtime.evaluate', {{expression: {json.dumps(js_read)}}});
                const val = res?.result?.result?.value || '';
                if (val && val === answer && val.length > 10) {{ break; }}
                answer = val;
            }}
            console.log(JSON.stringify({{answer}}));
            ws.close();
        }});
        """
        r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=90)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout.strip()).get("answer", "")
    except Exception:
        pass
    return None


def query_m1(prompt):
    """Query M1 local LM Studio."""
    data = {"model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.2, "max_output_tokens": 1024, "stream": False, "store": False}
    resp = _req(M1_URL, data, timeout=30)
    if resp and "output" in resp:
        for block in reversed(resp["output"]):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        return c.get("text", "")
    return None


def store_result(query, answer, source="chatgpt"):
    """Store in etoile.db memories table."""
    try:
        db = sqlite3.connect(os.path.normpath(DB_PATH))
        db.execute("""CREATE TABLE IF NOT EXISTS memories
            (id INTEGER PRIMARY KEY, category TEXT, key TEXT, value TEXT, created_at TEXT)""")
        db.execute("INSERT INTO memories (category, key, value, created_at) VALUES (?,?,?,?)",
                   ("chatgpt_dispatch", f"{source}:{query[:80]}", answer[:4000], datetime.now().isoformat()))
        db.commit()
        db.close()
        return True
    except Exception:
        return False


def run_query(query):
    answer = send_to_chatgpt(query)
    stored = False
    if answer:
        stored = store_result(query, answer)
    else:
        store_result(query, "[QUEUED] CDP failed — manual execution needed", "queue")
        return {"status": "queued", "query": query, "reason": "CDP unavailable"}
    return {"status": "ok", "source": "chatgpt", "query": query, "answer": answer, "stored": stored}


def run_research(topic):
    prompt = f"Deep research on: {topic}. Provide comprehensive analysis with sources."
    return run_query(prompt)


def run_compare(query):
    cgpt = send_to_chatgpt(query)
    m1 = query_m1(query)
    if cgpt:
        store_result(query, cgpt, "chatgpt")
    if m1:
        store_result(query, m1, "m1")
    return {"status": "ok", "query": query,
            "chatgpt": cgpt or "[unavailable]", "m1": m1 or "[unavailable]",
            "match": cgpt and m1 and (cgpt[:100].lower() == m1[:100].lower())}


def run_batch(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            queries = json.load(f)
    except Exception as e:
        return {"status": "error", "error": str(e)}
    results = []
    for q in queries:
        query = q if isinstance(q, str) else q.get("query", "")
        if query:
            results.append(run_query(query))
    return {"status": "ok", "count": len(results), "results": results}


def main():
    p = argparse.ArgumentParser(description="ChatGPT CDP Dispatcher")
    p.add_argument("--once", action="store_true", help="Run once and exit")
    p.add_argument("--query", type=str, help="Send query to ChatGPT")
    p.add_argument("--research", type=str, help="Deep research topic")
    p.add_argument("--compare", type=str, help="Compare ChatGPT vs M1")
    p.add_argument("--batch", type=str, help="Batch queries from JSON file")
    args = p.parse_args()

    if not any([args.query, args.research, args.compare, args.batch]):
        p.print_help()
        sys.exit(1)

    if args.query:
        result = run_query(args.query)
    elif args.research:
        result = run_research(args.research)
    elif args.compare:
        result = run_compare(args.compare)
    elif args.batch:
        result = run_batch(args.batch)
    else:
        result = {"status": "error", "error": "No action specified"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
