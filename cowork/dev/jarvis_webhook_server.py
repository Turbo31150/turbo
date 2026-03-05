#!/usr/bin/env python3
"""jarvis_webhook_server.py (#192) — Webhook server stdlib HTTP.

Serveur HTTP port 9801 avec routes /webhook/github, /webhook/trading, /webhook/alert.
Parse JSON body, log dans SQLite.

Usage:
    python dev/jarvis_webhook_server.py --once
    python dev/jarvis_webhook_server.py --start
    python dev/jarvis_webhook_server.py --stop
    python dev/jarvis_webhook_server.py --routes
    python dev/jarvis_webhook_server.py --test
"""
import argparse
import json
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "webhook_server.db"
PID_FILE = DEV / "data" / "webhook_server.pid"
PORT = 9801
HOST = "127.0.0.1"

ROUTES = {
    "/webhook/github": {
        "description": "GitHub webhook events (push, PR, issues)",
        "methods": ["POST"],
        "fields": ["action", "repository", "sender"]
    },
    "/webhook/trading": {
        "description": "Trading signal webhooks (buy/sell alerts)",
        "methods": ["POST"],
        "fields": ["signal", "pair", "price", "score"]
    },
    "/webhook/alert": {
        "description": "Generic alert webhooks (system, monitoring)",
        "methods": ["POST"],
        "fields": ["level", "message", "source"]
    },
    "/webhook/status": {
        "description": "Server status and recent events",
        "methods": ["GET"],
        "fields": []
    }
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        route TEXT,
        method TEXT,
        source_ip TEXT,
        headers_json TEXT,
        body_json TEXT,
        body_size INTEGER,
        processed INTEGER DEFAULT 0,
        response_code INTEGER DEFAULT 200
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS server_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        details TEXT
    )""")
    db.commit()
    return db


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhooks."""

    db_lock = threading.Lock()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/webhook/status":
            self._handle_status()
        elif path == "/health":
            self._send_json(200, {"status": "ok", "port": PORT, "uptime": "running"})
        elif path == "/routes":
            self._send_json(200, {"status": "ok", "routes": ROUTES})
        else:
            self._send_json(404, {"status": "error", "error": f"Unknown route: {path}"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path not in ROUTES:
            self._send_json(404, {"status": "error", "error": f"Unknown webhook: {path}"})
            return

        if "POST" not in ROUTES[path]["methods"]:
            self._send_json(405, {"status": "error", "error": "Method not allowed"})
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body_raw = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            body = json.loads(body_raw) if body_raw else {}
        except json.JSONDecodeError:
            body = {"raw": body_raw.decode("utf-8", errors="replace")}

        # Store headers (filtered)
        headers = {}
        for key in ["Content-Type", "User-Agent", "X-GitHub-Event",
                     "X-GitHub-Delivery", "X-Forwarded-For"]:
            val = self.headers.get(key)
            if val:
                headers[key] = val

        source_ip = self.client_address[0]

        # Log to DB
        with self.db_lock:
            try:
                db = sqlite3.connect(str(DB_PATH))
                db.execute(
                    """INSERT INTO webhook_events
                       (ts, route, method, source_ip, headers_json, body_json, body_size, response_code)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (time.time(), path, "POST", source_ip,
                     json.dumps(headers, ensure_ascii=False),
                     json.dumps(body, ensure_ascii=False),
                     content_length, 200)
                )
                db.commit()
                event_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.close()
            except Exception:
                event_id = -1

        self._send_json(200, {
            "status": "ok",
            "route": path,
            "event_id": event_id,
            "received_bytes": content_length,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    def _handle_status(self):
        """Return server status and recent events."""
        try:
            db = sqlite3.connect(str(DB_PATH))
            total = db.execute("SELECT COUNT(*) FROM webhook_events").fetchone()[0]
            recent = db.execute(
                "SELECT ts, route, source_ip, body_size FROM webhook_events ORDER BY ts DESC LIMIT 10"
            ).fetchall()
            route_counts = db.execute(
                "SELECT route, COUNT(*) FROM webhook_events GROUP BY route"
            ).fetchall()
            db.close()

            self._send_json(200, {
                "status": "ok",
                "total_events": total,
                "by_route": {r[0]: r[1] for r in route_counts},
                "recent": [
                    {
                        "ts": datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S"),
                        "route": r[1], "ip": r[2], "size": r[3]
                    }
                    for r in recent
                ]
            })
        except Exception as e:
            self._send_json(500, {"status": "error", "error": str(e)})


def start_server(db, foreground=False):
    """Start the webhook server."""
    # Check if already running
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object Id"],
                capture_output=True, text=True, timeout=5
            )
            if str(pid) in out.stdout:
                return {
                    "status": "info",
                    "message": f"Server already running on port {PORT} (PID {pid})",
                    "url": f"http://{HOST}:{PORT}"
                }
        except Exception:
            pass

    if not foreground:
        # Start in background
        proc = subprocess.Popen(
            [sys.executable, __file__, "--start", "--foreground"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        PID_FILE.write_text(str(proc.pid))

        db.execute(
            "INSERT INTO server_log (ts, action, details) VALUES (?,?,?)",
            (time.time(), "start", f"PID {proc.pid}, port {PORT}")
        )
        db.commit()

        return {
            "status": "ok",
            "message": f"Webhook server started on port {PORT}",
            "pid": proc.pid,
            "url": f"http://{HOST}:{PORT}",
            "routes": list(ROUTES.keys())
        }
    else:
        # Run in foreground
        PID_FILE.write_text(str(subprocess.os.getpid()))

        server = HTTPServer((HOST, PORT), WebhookHandler)

        def shutdown_handler(sig, frame):
            server.shutdown()
            PID_FILE.unlink(missing_ok=True)
            sys.exit(0)

        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            PID_FILE.unlink(missing_ok=True)
        return {"status": "ok", "message": "Server stopped"}


def stop_server(db):
    """Stop the webhook server."""
    if not PID_FILE.exists():
        return {"status": "info", "message": "Server not running (no PID file)"}

    try:
        pid = int(PID_FILE.read_text().strip())
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
            capture_output=True, text=True, timeout=10
        )
        PID_FILE.unlink(missing_ok=True)

        db.execute(
            "INSERT INTO server_log (ts, action, details) VALUES (?,?,?)",
            (time.time(), "stop", f"PID {pid}")
        )
        db.commit()

        return {"status": "ok", "message": f"Server stopped (PID {pid})"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def show_routes():
    """Show all routes."""
    return {
        "status": "ok",
        "host": HOST,
        "port": PORT,
        "routes": {
            route: {
                "description": info["description"],
                "methods": info["methods"],
                "expected_fields": info["fields"]
            }
            for route, info in ROUTES.items()
        }
    }


def test_webhooks(db):
    """Test webhook endpoints by sending test payloads."""
    import urllib.request

    results = []

    tests = [
        {
            "route": "/webhook/github",
            "payload": {"action": "push", "repository": "test/repo", "sender": "jarvis"}
        },
        {
            "route": "/webhook/trading",
            "payload": {"signal": "buy", "pair": "BTC/USDT", "price": 95000, "score": 85}
        },
        {
            "route": "/webhook/alert",
            "payload": {"level": "info", "message": "Test alert", "source": "self_test"}
        }
    ]

    for test in tests:
        url = f"http://{HOST}:{PORT}{test['route']}"
        data = json.dumps(test["payload"]).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read())
                results.append({
                    "route": test["route"],
                    "status": "ok",
                    "response": body,
                    "http_code": resp.status
                })
        except Exception as e:
            results.append({
                "route": test["route"],
                "status": "error",
                "error": str(e)
            })

    all_ok = all(r["status"] == "ok" for r in results)
    return {
        "status": "ok" if all_ok else "partial",
        "tests": results,
        "passed": sum(1 for r in results if r["status"] == "ok"),
        "total": len(results)
    }


def once(db):
    """Run once: show routes and stats."""
    total = 0
    by_route = {}
    try:
        total = db.execute("SELECT COUNT(*) FROM webhook_events").fetchone()[0]
        rows = db.execute("SELECT route, COUNT(*) FROM webhook_events GROUP BY route").fetchall()
        by_route = {r[0]: r[1] for r in rows}
    except Exception:
        pass

    return {
        "status": "ok",
        "mode": "once",
        "script": "jarvis_webhook_server.py (#192)",
        "server": {
            "host": HOST,
            "port": PORT,
            "pid_file": str(PID_FILE)
        },
        "routes": show_routes()["routes"],
        "stats": {
            "total_events": total,
            "by_route": by_route
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="jarvis_webhook_server.py (#192) — Webhook server HTTP stdlib"
    )
    parser.add_argument("--start", action="store_true",
                        help="Start webhook server on port 9801")
    parser.add_argument("--foreground", action="store_true",
                        help=argparse.SUPPRESS)  # Internal: run in foreground
    parser.add_argument("--stop", action="store_true",
                        help="Stop webhook server")
    parser.add_argument("--routes", action="store_true",
                        help="Show available routes")
    parser.add_argument("--test", action="store_true",
                        help="Test webhook endpoints")
    parser.add_argument("--once", action="store_true",
                        help="Run once: show routes and stats")
    args = parser.parse_args()

    db = init_db()

    if args.start:
        result = start_server(db, foreground=args.foreground)
    elif args.stop:
        result = stop_server(db)
    elif args.routes:
        result = show_routes()
    elif args.test:
        result = test_webhooks(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    if not (args.start and args.foreground):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
