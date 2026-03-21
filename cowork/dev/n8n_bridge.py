#!/usr/bin/env python3
"""n8n_bridge.py — Bridge cowork tasks to n8n workflows via HTTP API.

Connects to n8n at http://127.0.0.1:5678/api/v1/workflows to list, trigger,
and collect results. All operations logged to etoile.db.

CLI:
    --once              : list all workflows (JSON output)
    --trigger ID        : trigger workflow by ID, collect result
    --api-key KEY       : n8n API key (or N8N_API_KEY env var)

Stdlib-only (sqlite3, json, argparse, urllib).
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime
from _paths import ETOILE_DB

N8N_BASE = "http://127.0.0.1:5678"
API_V1 = "/api/v1"


def get_conn():
    conn = sqlite3.connect(str(ETOILE_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS n8n_bridge_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
        workflow_id TEXT, payload TEXT, response TEXT,
        success INTEGER DEFAULT 0, timestamp TEXT DEFAULT (datetime('now')))""")
    conn.commit()
    return conn


def api_request(path: str, method: str = "GET", data: dict = None,
                api_key: str = "") -> dict:
    url = f"{N8N_BASE}{path}"
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        hdrs["X-N8N-API-KEY"] = api_key
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return {"ok": True, "status": resp.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        return {"ok": False, "status": e.code, "error": str(e), "body": err_body}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}


def log_action(conn, action: str, wf_id: str, payload: str, response: str, ok: bool):
    conn.execute("INSERT INTO n8n_bridge_log (action,workflow_id,payload,response,success) "
                 "VALUES (?,?,?,?,?)", (action, wf_id, payload, response[:2000], int(ok)))
    conn.commit()


def list_workflows(api_key: str) -> dict:
    res = api_request(f"{API_V1}/workflows", api_key=api_key)
    if res["ok"]:
        wfs = res["data"].get("data", res["data"])
        if isinstance(wfs, list):
            return {"ok": True, "count": len(wfs), "workflows": [
                {"id": w.get("id"), "name": w.get("name"), "active": w.get("active")}
                for w in wfs]}
    return res


def trigger_workflow(wf_id: str, api_key: str) -> dict:
    payload = {"source": "n8n_bridge", "ts": datetime.utcnow().isoformat()}
    res = api_request(f"/webhook/{wf_id}", "POST", payload, api_key)
    if res["ok"]:
        return {"ok": True, "method": "webhook", "result": res["data"]}
    res2 = api_request(f"{API_V1}/workflows/{wf_id}/activate", "POST", api_key=api_key)
    if res2["ok"]:
        return {"ok": True, "method": "activate", "result": res2["data"]}
    return {"ok": False, "error": f"webhook:{res.get('error')}, activate:{res2.get('error')}"}


def run_list(api_key: str) -> dict:
    conn = get_conn()
    try:
        res = list_workflows(api_key)
        log_action(conn, "list", "", "", json.dumps(res)[:2000], res.get("ok", False))
        return {"timestamp": datetime.utcnow().isoformat() + "Z", "action": "list", **res}
    finally:
        conn.close()


def run_trigger(wf_id: str, api_key: str) -> dict:
    conn = get_conn()
    try:
        res = trigger_workflow(wf_id, api_key)
        log_action(conn, "trigger", wf_id, json.dumps({"id": wf_id}),
                   json.dumps(res)[:2000], res.get("ok", False))
        conn.execute(
            "INSERT INTO memories (category,key,value,source,confidence) VALUES (?,?,?,?,?)",
            ("n8n_bridge", f"trigger_{wf_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
             json.dumps(res)[:2000], "n8n_bridge.py", 1.0 if res.get("ok") else 0.3))
        conn.commit()
        return {"timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "trigger", "workflow_id": wf_id, **res}
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="n8n workflow bridge for JARVIS cowork")
    ap.add_argument("--once", action="store_true", help="List workflows")
    ap.add_argument("--trigger", type=str, default="", help="Trigger workflow by ID")
    ap.add_argument("--api-key", type=str, default="", help="n8n API key (or N8N_API_KEY env)")
    args = ap.parse_args()
    api_key = args.api_key or os.environ.get("N8N_API_KEY", "")
    if args.trigger:
        print(json.dumps(run_trigger(args.trigger, api_key), indent=2))
    elif args.once:
        print(json.dumps(run_list(api_key), indent=2))
    else:
        ap.print_help(); sys.exit(1)


if __name__ == "__main__":
    main()
