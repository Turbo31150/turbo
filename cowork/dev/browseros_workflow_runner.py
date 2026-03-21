#!/usr/bin/env python3
"""BrowserOS Workflow Runner — Execute and chain BrowserOS MCP workflows.

stdlib-only, argparse --once, JSON output.
Modes: --workflow NAME, --list, --create NAME STEPS.
"""
import argparse, json, time, sqlite3, os, sys
import urllib.request, urllib.error
from datetime import datetime

MCP_URL = "http://127.0.0.1:9000/mcp"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "etoile.db")
WORKFLOWS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "workflows.json")
DEFAULT_DELAY = 3
RPC_ID = 0


def _next_id():
    global RPC_ID
    RPC_ID += 1
    return RPC_ID


def mcp_call(tool_name, arguments=None, timeout=30):
    """Call a BrowserOS MCP tool via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments or {}}
    }
    try:
        req = urllib.request.Request(MCP_URL, headers={"Content-Type": "application/json"})
        body = json.dumps(payload).encode()
        with urllib.request.urlopen(req, body, timeout=timeout) as r:
            resp = json.loads(r.read().decode())
            if "result" in resp:
                return {"ok": True, "data": resp["result"]}
            elif "error" in resp:
                return {"ok": False, "error": resp["error"]}
            return {"ok": True, "data": resp}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- Pre-defined workflows ---

BUILTIN_WORKFLOWS = {
    "linkedin_engage": {
        "description": "Open LinkedIn, snapshot, find and click likes, verify",
        "steps": [
            {"tool": "new_page", "args": {"url": "https://www.linkedin.com/feed/"}, "delay": 5},
            {"tool": "take_snapshot", "args": {}, "delay": 2},
            {"tool": "get_page_content", "args": {}, "delay": 1},
            {"tool": "evaluate_script", "args": {"expression": """
                (function() {
                    let btns = document.querySelectorAll('button[aria-label*="Like"], button[aria-label*="J\\'aime"]');
                    let clicked = 0;
                    btns.forEach((b, i) => { if (i < 5) { b.click(); clicked++; } });
                    return 'Liked ' + clicked + ' posts';
                })()
            """}, "delay": 3},
            {"tool": "take_snapshot", "args": {}, "delay": 1},
            {"tool": "get_page_content", "args": {}, "delay": 0}
        ]
    },
    "codeur_scan": {
        "description": "Scan codeur.com projects, extract listings",
        "steps": [
            {"tool": "new_page", "args": {"url": "https://www.codeur.com/projects"}, "delay": 5},
            {"tool": "get_page_content", "args": {}, "delay": 2},
            {"tool": "evaluate_script", "args": {"expression": """
                (function() {
                    let projects = [];
                    document.querySelectorAll('.project-item, .card, article').forEach(el => {
                        let title = el.querySelector('h2, h3, .title');
                        let link = el.querySelector('a');
                        if (title) projects.push({
                            title: title.textContent.trim(),
                            url: link ? link.href : ''
                        });
                    });
                    return JSON.stringify(projects.slice(0, 20));
                })()
            """}, "delay": 1},
            {"tool": "take_snapshot", "args": {}, "delay": 0}
        ]
    },
    "github_review": {
        "description": "Open GitHub notifications, read and summarize",
        "steps": [
            {"tool": "new_page", "args": {"url": "https://github.com/notifications"}, "delay": 5},
            {"tool": "take_snapshot", "args": {}, "delay": 2},
            {"tool": "get_page_content", "args": {}, "delay": 1},
            {"tool": "evaluate_script", "args": {"expression": """
                (function() {
                    let notifs = [];
                    document.querySelectorAll('.notification-list-item, .notifications-list-item').forEach(n => {
                        let title = n.querySelector('.markdown-title, a');
                        let repo = n.querySelector('.text-small, .repo-name');
                        if (title) notifs.push({
                            title: title.textContent.trim(),
                            repo: repo ? repo.textContent.trim() : '',
                            url: title.href || ''
                        });
                    });
                    return JSON.stringify(notifs.slice(0, 15));
                })()
            """}, "delay": 0}
        ]
    },
    "multi_search": {
        "description": "Search on Google then Perplexity, compare results",
        "steps": [
            {"tool": "new_page", "args": {"url": "https://www.google.com"}, "delay": 4},
            {"tool": "take_snapshot", "args": {}, "delay": 1},
            {"tool": "fill", "args": {"selector": "textarea[name='q'], input[name='q']", "value": "{{query}}"}, "delay": 1},
            {"tool": "press_key", "args": {"key": "Enter"}, "delay": 4},
            {"tool": "get_page_content", "args": {}, "save_as": "google_results", "delay": 2},
            {"tool": "new_page", "args": {"url": "https://www.perplexity.ai"}, "delay": 5},
            {"tool": "take_snapshot", "args": {}, "delay": 1},
            {"tool": "fill", "args": {"selector": "textarea", "value": "{{query}}"}, "delay": 1},
            {"tool": "press_key", "args": {"key": "Enter"}, "delay": 8},
            {"tool": "get_page_content", "args": {}, "save_as": "perplexity_results", "delay": 0}
        ]
    }
}


def load_custom_workflows():
    """Load user-created workflows from disk."""
    path = os.path.normpath(WORKFLOWS_PATH)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_custom_workflows(workflows):
    """Persist user-created workflows."""
    path = os.path.normpath(WORKFLOWS_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflows, f, indent=2, ensure_ascii=False)


def get_all_workflows():
    custom = load_custom_workflows()
    merged = dict(BUILTIN_WORKFLOWS)
    merged.update(custom)
    return merged


def store_result(workflow_name, results):
    """Store workflow results in etoile.db memories."""
    try:
        db = sqlite3.connect(os.path.normpath(DB_PATH))
        db.execute("""CREATE TABLE IF NOT EXISTS memories
            (id INTEGER PRIMARY KEY, category TEXT, key TEXT, value TEXT, created_at TEXT)""")
        summary = json.dumps(results, ensure_ascii=False)[:4000]
        db.execute("INSERT INTO memories (category, key, value, created_at) VALUES (?,?,?,?)",
                   ("browseros_workflow", workflow_name, summary, datetime.now().isoformat()))
        db.commit()
        db.close()
        return True
    except Exception:
        return False


def resolve_template(value, variables):
    """Replace {{var}} placeholders in strings."""
    if isinstance(value, str):
        for k, v in variables.items():
            value = value.replace(f"{{{{{k}}}}}", str(v))
    elif isinstance(value, dict):
        return {dk: resolve_template(dv, variables) for dk, dv in value.items()}
    return value


def run_workflow(name, variables=None):
    """Execute a named workflow step by step."""
    variables = variables or {}
    all_wf = get_all_workflows()
    if name not in all_wf:
        return {"status": "error", "error": f"Unknown workflow: {name}",
                "available": list(all_wf.keys())}

    wf = all_wf[name]
    steps = wf.get("steps", [])
    results = []
    saved_outputs = {}

    for i, step in enumerate(steps):
        tool = step["tool"]
        args = resolve_template(step.get("args", {}), variables)
        delay = step.get("delay", DEFAULT_DELAY)
        save_as = step.get("save_as")

        result = mcp_call(tool, args)
        entry = {"step": i + 1, "tool": tool, "result": result}
        results.append(entry)

        if save_as and result.get("ok"):
            saved_outputs[save_as] = result.get("data")

        if delay > 0:
            time.sleep(delay)

    stored = store_result(name, results)
    return {"status": "ok", "workflow": name, "steps_run": len(results),
            "results": results, "saved_outputs": saved_outputs, "stored": stored}


def list_workflows():
    """List all available workflows."""
    all_wf = get_all_workflows()
    listing = {}
    for name, wf in all_wf.items():
        listing[name] = {
            "description": wf.get("description", ""),
            "steps": len(wf.get("steps", [])),
            "builtin": name in BUILTIN_WORKFLOWS
        }
    return {"status": "ok", "workflows": listing, "count": len(listing)}


def create_workflow(name, steps_json):
    """Create a new custom workflow from JSON steps."""
    try:
        steps = json.loads(steps_json) if isinstance(steps_json, str) else steps_json
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"Invalid JSON: {e}"}

    if not isinstance(steps, list) or len(steps) == 0:
        return {"status": "error", "error": "Steps must be a non-empty JSON array"}

    # Validate step structure
    for i, s in enumerate(steps):
        if "tool" not in s:
            return {"status": "error", "error": f"Step {i+1} missing 'tool' field"}

    custom = load_custom_workflows()
    custom[name] = {"description": f"Custom workflow: {name}", "steps": steps}
    save_custom_workflows(custom)
    return {"status": "ok", "workflow": name, "steps": len(steps), "message": "Workflow created"}


def main():
    p = argparse.ArgumentParser(description="BrowserOS MCP Workflow Runner")
    p.add_argument("--once", action="store_true", help="Run once and exit")
    p.add_argument("--workflow", type=str, help="Run named workflow")
    p.add_argument("--list", action="store_true", help="List available workflows")
    p.add_argument("--create", nargs=2, metavar=("NAME", "STEPS_JSON"),
                   help="Create new workflow: NAME 'JSON_STEPS'")
    p.add_argument("--var", action="append", metavar="KEY=VALUE",
                   help="Template variable (e.g. --var query=AI)")
    args = p.parse_args()

    if not any([args.workflow, args.list, args.create]):
        p.print_help()
        sys.exit(1)

    # Parse variables
    variables = {}
    if args.var:
        for v in args.var:
            if "=" in v:
                k, val = v.split("=", 1)
                variables[k] = val

    if args.list:
        result = list_workflows()
    elif args.create:
        result = create_workflow(args.create[0], args.create[1])
    elif args.workflow:
        result = run_workflow(args.workflow, variables)
    else:
        result = {"status": "error", "error": "No action specified"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
