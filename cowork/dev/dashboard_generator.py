#!/usr/bin/env python3
"""dashboard_generator.py

Generate a static dashboard with system, cluster and trading metrics.

Usage:
  dashboard_generator.py [options]

Options:
  --html       Output an HTML dashboard to stdout.
  --json       Output metrics as JSON to stdout.
  --serve      Serve the current directory via SimpleHTTPServer on port 8888.
  -h, --help   Show this help message.

The script uses only the Python standard library.
"""

import argparse
import json
import os
import platform
import sys
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer


def collect_system_metrics():
    """Collect basic system metrics using the stdlib.
    Returns a dict with OS info, uptime, and CPU load (if available)."""
    metrics = {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }
    # Uptime (seconds since boot)
    try:
        if sys.platform.startswith("win"):
            # Use net stats workstation command
            import subprocess
            out = subprocess.check_output(["net", "stats", "workstation"], shell=True, text=True)
            for line in out.splitlines():
                if "since" in line.lower():
                    # crude extraction
                    metrics["uptime"] = line.strip()
                    break
        else:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
                metrics["uptime_seconds"] = int(uptime_seconds)
    except Exception:
        metrics["uptime_seconds"] = None
    # Load average (Unix only)
    try:
        if hasattr(os, "getloadavg"):
            load1, load5, load15 = os.getloadavg()
            metrics["load_average"] = {"1": load1, "5": load5, "15": load15}
    except Exception:
        metrics["load_average"] = None
    return metrics


def collect_cluster_metrics():
    """Placeholder for cluster metrics. Returns an empty dict for now."""
    return {}


def collect_trading_metrics():
    """Placeholder for trading metrics. Returns an empty dict for now."""
    return {}


def build_metrics():
    return {
        "system": collect_system_metrics(),
        "cluster": collect_cluster_metrics(),
        "trading": collect_trading_metrics(),
    }


def metrics_to_html(metrics):
    html = """<html><head><title>Dashboard</title></head><body>"""
    html += "<h1>System Metrics</h1><pre>{}</pre>".format(json.dumps(metrics.get("system", {}), indent=2))
    html += "<h1>Cluster Metrics</h1><pre>{}</pre>".format(json.dumps(metrics.get("cluster", {}), indent=2))
    html += "<h1>Trading Metrics</h1><pre>{}</pre>".format(json.dumps(metrics.get("trading", {}), indent=2))
    html += "</body></html>"
    return html


def serve(port=8888):
    handler = SimpleHTTPRequestHandler
    httpd = HTTPServer(("", port), handler)
    print(f"Serving HTTP on port {port} (http://127.0.0.1:{port}/) ...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="Generate a static dashboard with system, cluster and trading metrics.")
    parser.add_argument("--html", action="store_true", help="Output HTML to stdout")
    parser.add_argument("--json", action="store_true", help="Output metrics as JSON to stdout")
    parser.add_argument("--serve", action="store_true", help="Serve current directory via SimpleHTTPServer on port 8888")
    args = parser.parse_args()

    if args.serve:
        serve()
        return

    metrics = build_metrics()
    if args.json:
        print(json.dumps(metrics, indent=2))
    if args.html:
        print(metrics_to_html(metrics))
    if not any([args.json, args.html, args.serve]):
        parser.print_help()


if __name__ == "__main__":
    main()
