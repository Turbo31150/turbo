"""jarvis_desktop_dashboard.py — Dashboard desktop interactif JARVIS.

Serveur HTTP local (127.0.0.1 uniquement) qui affiche un dashboard temps reel.
Les donnees proviennent exclusivement de sources locales de confiance (nvidia-smi,
systemctl, /proc). Aucune donnee utilisateur externe n'est rendue dans le HTML.

Usage:
    python scripts/jarvis_desktop_dashboard.py
    # Ouvrir http://127.0.0.1:8088
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8088
JARVIS_HOME = Path(__file__).resolve().parent.parent

# Liste blanche des actions autorisees
ALLOWED_ACTIONS = {"restart-voice", "backup", "dashboard", "learn", "gpu", "db"}
# Liste blanche des services JARVIS autorisees
ALLOWED_SERVICE_PREFIX = "jarvis-"
ALLOWED_SERVICE_ACTIONS = {"start", "stop", "restart"}


def _run(cmd, timeout=5):
    """Execute une commande et retourne stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def get_system_data() -> dict:
    """Collecte les donnees systeme depuis des sources locales de confiance."""
    data = {"ts": time.time()}

    # CPU load
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            data["load"] = {"m1": parts[0], "m5": parts[1], "m15": parts[2]}
    except Exception:
        data["load"] = {"m1": "?", "m5": "?", "m15": "?"}

    # RAM
    try:
        output = _run(["free", "-b"])
        for line in output.split("\n"):
            if line.startswith("Mem:"):
                parts = line.split()
                total, used = int(parts[1]), int(parts[2])
                data["ram"] = {"used_gb": round(used / 1e9, 1), "total_gb": round(total / 1e9, 1),
                               "pct": round(used / total * 100, 1)}
    except Exception:
        data["ram"] = {"used_gb": 0, "total_gb": 0, "pct": 0}

    # GPUs
    data["gpus"] = []
    try:
        output = _run(["nvidia-smi",
            "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total,fan.speed,power.draw",
            "--format=csv,noheader,nounits"])
        for line in output.split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 8:
                data["gpus"].append({
                    "id": int(parts[0]), "name": parts[1][:20],
                    "temp": int(parts[2]), "util": int(parts[3]),
                    "vram_used": int(parts[4]), "vram_total": int(parts[5]),
                    "fan": parts[6], "power": parts[7],
                })
    except Exception:
        pass

    # Services
    data["services"] = []
    try:
        output = _run(["systemctl", "--user", "list-units", "jarvis-*", "--no-pager", "--no-legend"])
        for line in output.split("\n"):
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0].replace(".service", "")
                active = "running" in line
                data["services"].append({"name": name, "active": active})
    except Exception:
        pass

    # Cluster
    data["cluster"] = {}
    for node, url in [("M1", "http://127.0.0.1:1234/api/v1/models"), ("OL1", "http://127.0.0.1:11434/api/tags")]:
        try:
            r = subprocess.run(["curl", "-s", "--max-time", "2", url], capture_output=True, text=True, timeout=3)
            data["cluster"][node] = r.returncode == 0 and len(r.stdout) > 10
        except Exception:
            data["cluster"][node] = False

    # Uptime
    data["uptime"] = _run(["uptime", "-p"]).replace("up ", "")

    # Disk
    try:
        output = _run(["df", "-h", "/"])
        lines = output.split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            data["disk"] = {"used": parts[2], "total": parts[1], "pct": parts[4]}
    except Exception:
        data["disk"] = {"used": "?", "total": "?", "pct": "?"}

    return data


def get_dashboard_html() -> str:
    """Retourne le HTML du dashboard. Contenu statique, donnees via API JSON."""
    return Path(JARVIS_HOME / "scripts" / "dashboard.html").read_text(encoding="utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            try:
                html = get_dashboard_html()
            except FileNotFoundError:
                html = "<h1>JARVIS Dashboard</h1><p>dashboard.html not found</p>"
            self.wfile.write(html.encode("utf-8"))

        elif parsed.path == "/api/data":
            self._json_response(get_system_data())

        elif parsed.path == "/api/service":
            params = parse_qs(parsed.query)
            name = params.get("name", [""])[0]
            action = params.get("action", ["restart"])[0]
            # Validation stricte
            if not name.startswith(ALLOWED_SERVICE_PREFIX) or action not in ALLOWED_SERVICE_ACTIONS:
                self._json_response({"error": "forbidden"}, 403)
                return
            _run(["systemctl", "--user", action, f"{name}.service"], timeout=10)
            self._json_response({"ok": True, "name": name, "action": action})

        elif parsed.path == "/api/action":
            params = parse_qs(parsed.query)
            cmd = params.get("cmd", [""])[0]
            if cmd not in ALLOWED_ACTIONS:
                self._json_response({"error": "forbidden"}, 403)
                return
            result = ""
            if cmd == "restart-voice":
                _run(["systemctl", "--user", "restart", "jarvis-voice"], timeout=10)
                result = "Voice pipeline redemarré"
            elif cmd in ("backup", "dashboard", "learn", "gpu", "db"):
                result = _run(["/usr/local/bin/jarvis", cmd.replace("dashboard", "dash")], timeout=30)
            self._json_response({"ok": True, "cmd": cmd, "result": result})

        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    print(f"JARVIS Desktop Dashboard — http://127.0.0.1:{PORT}")
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard arrete")
        server.server_close()
