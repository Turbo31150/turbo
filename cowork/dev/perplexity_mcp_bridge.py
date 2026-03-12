#!/usr/bin/env python3
"""perplexity_mcp_bridge.py — Stub that checks if Perplexity MCP is reachable.

Probes the Perplexity MCP endpoint (if configured) and reports its status.
Useful for monitoring MCP service availability in the JARVIS cluster.

Usage:
    python dev/perplexity_mcp_bridge.py --once
    python dev/perplexity_mcp_bridge.py --once --port 8100
    python dev/perplexity_mcp_bridge.py --dry-run
"""
import argparse
import json
import socket
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_DIR / "data"

# Default Perplexity MCP configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8100
DEFAULT_TIMEOUT = 5

# Known MCP config locations
MCP_CONFIG_PATHS = [
    Path("C:/Users/franc/.claude/.mcp.json"),
    Path("C:/Users/franc/.claude/settings.json"),
    TURBO_DIR / ".mcp.json",
    TURBO_DIR / "mcp_config.json",
]


def find_perplexity_config() -> dict:
    """Search for Perplexity MCP configuration in known locations."""
    for config_path in MCP_CONFIG_PATHS:
        if not config_path.exists():
            continue
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            # Search for perplexity in MCP server configs
            servers = data.get("mcpServers", data.get("mcp_servers", {}))
            for name, conf in servers.items():
                if "perplexity" in name.lower():
                    return {
                        "found": True,
                        "config_file": str(config_path),
                        "server_name": name,
                        "config": conf,
                    }
        except (json.JSONDecodeError, OSError):
            continue

    return {"found": False, "config_file": None, "server_name": None, "config": None}


def check_port(host: str, port: int, timeout: float = 3.0) -> dict:
    """Check if a TCP port is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return {
            "reachable": result == 0,
            "host": host,
            "port": port,
            "error": None if result == 0 else f"Connection refused (code {result})",
        }
    except socket.timeout:
        return {"reachable": False, "host": host, "port": port, "error": "Timeout"}
    except OSError as e:
        return {"reachable": False, "host": host, "port": port, "error": str(e)}


def check_http_endpoint(host: str, port: int, timeout: float = 5.0) -> dict:
    """Try an HTTP health check on the endpoint."""
    url = f"http://{host}:{port}"
    for path in ["/health", "/status", "/", "/api/status"]:
        try:
            req = urllib.request.Request(url + path, method="GET")
            resp = urllib.request.urlopen(req, timeout=timeout)
            body = resp.read().decode("utf-8", errors="replace")[:500]
            return {
                "http_reachable": True,
                "url": url + path,
                "status_code": resp.status,
                "body_preview": body,
                "error": None,
            }
        except urllib.error.HTTPError as e:
            return {
                "http_reachable": True,
                "url": url + path,
                "status_code": e.code,
                "body_preview": None,
                "error": f"HTTP {e.code}: {e.reason}",
            }
        except (urllib.error.URLError, OSError):
            continue

    return {
        "http_reachable": False,
        "url": url,
        "status_code": None,
        "body_preview": None,
        "error": "No HTTP endpoints responded",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check Perplexity MCP bridge status"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Check without side effects")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="MCP host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="MCP port")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Timeout seconds")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    # Step 1: Search for config
    config_info = find_perplexity_config()

    # Extract host/port from config if found
    host = args.host
    port = args.port
    if config_info["found"] and config_info["config"]:
        conf = config_info["config"]
        # Try to extract port from various config formats
        if isinstance(conf, dict):
            port = conf.get("port", conf.get("serverPort", port))
            host = conf.get("host", conf.get("serverHost", host))

    # Step 2: TCP port check
    port_status = check_port(host, port, timeout=args.timeout)

    # Step 3: HTTP check (only if port is open)
    http_status = None
    if port_status["reachable"]:
        http_status = check_http_endpoint(host, port, timeout=args.timeout)

    # Build report
    report = {
        "config": config_info,
        "port_check": port_status,
        "http_check": http_status,
        "overall_status": "online" if port_status["reachable"] else "offline",
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if port_status["reachable"] else 1)

    # Human-readable output
    print("=== Perplexity MCP Bridge Status ===")
    print()

    if config_info["found"]:
        print(f"Config found: {config_info['config_file']}")
        print(f"Server name: {config_info['server_name']}")
    else:
        print("Config: Not found in known locations")
        print("  Checked: " + ", ".join(str(p) for p in MCP_CONFIG_PATHS))
    print()

    status_icon = "ONLINE" if port_status["reachable"] else "OFFLINE"
    print(f"TCP {host}:{port} — {status_icon}")
    if port_status["error"]:
        print(f"  Error: {port_status['error']}")

    if http_status:
        if http_status["http_reachable"]:
            print(f"HTTP {http_status['url']} — Status {http_status['status_code']}")
            if http_status["body_preview"]:
                preview = http_status["body_preview"][:100].replace("\n", " ")
                print(f"  Response: {preview}")
        else:
            print(f"HTTP — No endpoints responded")
    print()

    result = {
        "status": "ok" if port_status["reachable"] else "offline",
        "timestamp": datetime.now().isoformat(),
        "host": host,
        "port": port,
        "reachable": port_status["reachable"],
        "config_found": config_info["found"],
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
