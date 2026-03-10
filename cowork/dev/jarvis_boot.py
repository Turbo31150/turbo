#!/usr/bin/env python3
"""JARVIS Boot: check boot status and report phase details."""
import argparse
import json
import time
import sys
import urllib.request
import urllib.error

BOOT_URL = "http://127.0.0.1:9742/api/boot/status"


def fetch_boot_status(timeout: float = 10.0) -> dict:
    try:
        req = urllib.request.Request(BOOT_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def format_report(data: dict) -> dict:
    if "error" in data:
        return {"ok": False, "error": data["error"]}

    phases = data.get("phases", data.get("boot_phases", []))
    services = data.get("services", data.get("service_status", {}))
    status = data.get("status", data.get("state", "unknown"))
    uptime = data.get("uptime", data.get("uptime_sec", 0))

    phase_summary = []
    if isinstance(phases, list):
        for p in phases:
            phase_summary.append({
                "name": p.get("name", "?"),
                "status": p.get("status", "?"),
                "duration": p.get("duration", p.get("duration_sec", "?")),
            })
    elif isinstance(phases, dict):
        for name, info in phases.items():
            s = info if isinstance(info, str) else info.get("status", "?")
            phase_summary.append({"name": name, "status": s})

    svc_summary = {}
    if isinstance(services, dict):
        for name, info in services.items():
            if isinstance(info, dict):
                svc_summary[name] = info.get("status", info.get("alive", "?"))
            else:
                svc_summary[name] = info

    failed = [p["name"] for p in phase_summary if p.get("status") in ("failed", "error")]
    return {
        "ok": status in ("ready", "running", "ok", "complete"),
        "status": status,
        "uptime_sec": uptime,
        "phases": phase_summary,
        "services": svc_summary,
        "failed_phases": failed,
    }


def boot_cycle() -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    raw = fetch_boot_status()
    report = format_report(raw)
    report["timestamp"] = ts
    return report


def main():
    parser = argparse.ArgumentParser(description="JARVIS boot status reporter")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--interval", type=int, default=30, help="Loop interval (sec)")
    parser.add_argument("--wait-ready", action="store_true",
                        help="Loop until boot is ready, then exit")
    args = parser.parse_args()

    while True:
        result = boot_cycle()
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["ok"] else 1)
        if args.wait_ready and result["ok"]:
            sys.exit(0)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
