#!/usr/bin/env python3
"""win_task_automator.py
Utility to manage Windows scheduled tasks (schtasks) for JARVIS.

Supported sub-commands:
  --create  NAME   /TR "command" [/SC schedule] [/ST start_time] [/ED end_date]
  --list               List all JARVIS-managed tasks
  --delete  NAME       Delete a JARVIS-managed task
  --export  PATH       Export all JARVIS tasks to a JSON file
  --import  PATH       Import tasks from a JSON file (creates/updates)

Templates (pre-filled command strings) are provided for common JARVIS services:
  * LM Studio auto-start
  * Ollama auto-start
  * Backup health check

Typical usage:
  python win_task_automator.py --create "JARVIS_LM_Studio" /TR "C:\\Program Files\\LMStudio\\lmstudio.exe" /SC DAILY /ST 09:00
  python win_task_automator.py --list

The script only uses the Python standard library (subprocess, argparse, json, os, sys).
"""

import argparse, subprocess, json, os, sys

JARVIS_TAG = "[JARVIS]"

ALLOWED_COMMANDS = {"schtasks", "whoami"}

def run_cmd(cmd):
    base = cmd.split()[0].lower() if cmd.strip() else ""
    if base not in ALLOWED_COMMANDS:
        return "", f"Blocked: {base} not in allowed commands", 1
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def list_tasks():
    cmd = "schtasks /Query /FO LIST /V"
    out, err, rc = run_cmd(cmd)
    if rc != 0:
        print(f"Error listing tasks: {err}")
        sys.exit(1)
    tasks = []
    current = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                tasks.append(current)
                current = {}
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()
    if current:
        tasks.append(current)
    # Filter JARVIS tasks
    jarvis_tasks = [t for t in tasks if JARVIS_TAG in t.get("TaskName", "")]
    for t in jarvis_tasks:
        print(t.get("TaskName"))

def create_task(name, command, schedule="DAILY", start="09:00", end=None):
    # Prefix name with JARVIS tag for easy identification
    task_name = f"{JARVIS_TAG}_{name}"
    args = ["schtasks", "/Create", "/TN", task_name, "/TR", f'"{command}"', "/SC", schedule, "/ST", start]
    if end:
        args.extend(["/ED", end])
    cmd = " ".join(args)
    out, err, rc = run_cmd(cmd)
    if rc != 0:
        print(f"Failed to create task: {err}")
        sys.exit(1)
    print(out)

def delete_task(name):
    task_name = f"{JARVIS_TAG}_{name}"
    cmd = f"schtasks /Delete /TN {task_name} /F"
    out, err, rc = run_cmd(cmd)
    if rc != 0:
        print(f"Failed to delete task: {err}")
        sys.exit(1)
    print(out)

def export_tasks(path):
    cmd = "schtasks /Query /FO LIST /V"
    out, err, rc = run_cmd(cmd)
    if rc != 0:
        print(f"Error exporting tasks: {err}")
        sys.exit(1)
    tasks = []
    current = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                tasks.append(current)
                current = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            current[k.strip()] = v.strip()
    if current:
        tasks.append(current)
    jarvis_tasks = [t for t in tasks if JARVIS_TAG in t.get("TaskName", "")]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jarvis_tasks, f, indent=2)
    print(f"Exported {len(jarvis_tasks)} tasks to {path}")

def import_tasks(path):
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    for t in tasks:
        name = t.get("TaskName", "").replace(JARVIS_TAG+"_", "")
        cmd = t.get("TaskToRun")
        schedule = t.get("ScheduleType", "DAILY")
        start = t.get("StartTime", "09:00")
        create_task(name, cmd, schedule, start)
    print(f"Imported {len(tasks)} tasks from {path}")

def main():
    parser = argparse.ArgumentParser(description="Manage Windows scheduled tasks for JARVIS.")
    subparsers = parser.add_subparsers(dest="action")

    create = subparsers.add_parser("--create", help="Create a JARVIS task")
    create.add_argument("name", help="Task identifier")
    create.add_argument("--tr", dest="command", help="Command to run")
    create.add_argument("--sc", dest="schedule", default="DAILY", help="Schedule (HOURLY, DAILY, WEEKLY, ...)")
    create.add_argument("--st", dest="start", default="09:00", help="Start time (HH:MM)")
    create.add_argument("--ed", dest="end", default=None, help="End date (YYYY/MM/DD)")

    subparsers.add_parser("--list", help="List JARVIS tasks")
    subparsers.add_parser("--delete", help="Delete a JARVIS task").add_argument("name", help="Task identifier")
    exp = subparsers.add_parser("--export", help="Export tasks to JSON")
    exp.add_argument("path", help="Output file path")
    imp = subparsers.add_parser("--import", help="Import tasks from JSON")
    imp.add_argument("path", help="Input file path")

    args = parser.parse_args()
    if args.action == "--create":
        create_task(args.name, args.command, args.schedule, args.start, args.end)
    elif args.action == "--list":
        list_tasks()
    elif args.action == "--delete":
        delete_task(args.name)
    elif args.action == "--export":
        export_tasks(args.path)
    elif args.action == "--import":
        import_tasks(args.path)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
