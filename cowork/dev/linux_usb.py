#!/usr/bin/env python3
"""List USB devices via PowerShell Get-PnpDevice, output as JSON."""

import argparse
import json
import subprocess
import time


def query_usb_devices():
    """Run PowerShell to get USB devices."""
    ps_cmd = (
        "Get-PnpDevice -Class USB -ErrorAction SilentlyContinue | "
        "Select-Object Status, Class, FriendlyName, InstanceId, Manufacturer | "
        "ConvertTo-Json -Compress"
    )
    cmd = ["bash", "-NoProfile", "-Command", ps_cmd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return {"error": f"PowerShell failed: {result.stderr.strip()}"}
    except FileNotFoundError:
        return {"error": "PowerShell not found"}
    except subprocess.TimeoutExpired:
        return {"error": "PowerShell timed out (15s)"}

    output = result.stdout.strip()
    if not output:
        return {"devices": [], "count": 0}

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
        devices = []
        for d in data:
            devices.append({
                "name": d.get("FriendlyName", "Unknown"),
                "status": d.get("Status", "Unknown"),
                "class": d.get("Class", "USB"),
                "instance_id": d.get("InstanceId", ""),
                "manufacturer": d.get("Manufacturer", ""),
            })
        return {"devices": devices, "count": len(devices)}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": output[:500]}


def run_once():
    data = query_usb_devices()
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **data,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="List USB devices via PowerShell (JSON output)")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
