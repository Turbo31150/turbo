#!/usr/bin/env python3
"""Process Manager script for Windows.

Provides three subcommands:
  list               List running processes (PID, name, status).
  kill   <pid>       Kill a process by PID.
  restart <pid> <exe_path>
                     Restart a process: kill the PID and start the executable.

Usage examples:
  python process_manager.py list
  python process_manager.py kill 1234
  python process_manager.py restart 1234 "/\Program Files/MyApp/myapp.exe"

The script uses only the Python standard library and works on Windows.
"""

import argparse
import subprocess
import sys
import os
import shlex

def list_processes():
    # Use PowerShell Get-Process to list processes in a parsable format
    cmd = ["powershell.exe", "-Command", "Get-Process | Select-Object -Property Id, ProcessName, CPU, @{Name='MemoryMB';Expression={[math]::Round($_.WorkingSet64/1MB,1)}} | ConvertTo-Json -Depth 2"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error retrieving processes:", result.stderr, file=sys.stderr)
        return
    try:
        import json
        processes = json.loads(result.stdout)
        for p in processes:
            print(f"{p['Id']:>6}  {p['ProcessName']:<25}  CPU:{p.get('CPU','0'):.1f}  MEM:{p.get('MemoryMB','0')} MB")
    except Exception as e:
        print("Failed to parse process list:", e, file=sys.stderr)

def kill_process(pid: int):
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=True)
        print(f"Process {pid} killed.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to kill process {pid}: {e}", file=sys.stderr)

def restart_process(pid: int, exe_path: str):
    # Kill first
    kill_process(pid)
    # Start new process
    try:
        # Use startfile to launch, fallback to subprocess
        if os.path.isfile(exe_path):
            os.startfile(exe_path)
            print(f"Process restarted with {exe_path}.")
        else:
            # If path contains arguments, split
            args = shlex.split(exe_path)
            subprocess.Popen(args, shell=False)
            print(f"Process restarted with command: {exe_path}")
    except Exception as e:
        print(f"Failed to start process: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Windows Process Manager (list, kill, restart)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List running processes")

    kill_parser = subparsers.add_parser("kill", help="Kill a process by PID")
    kill_parser.add_argument("pid", type=int, help="Process ID to kill")

    restart_parser = subparsers.add_parser("restart", help="Restart a process")
    restart_parser.add_argument("pid", type=int, help="Process ID to kill before restart")
    restart_parser.add_argument("exe_path", help="Path to executable or command to launch")

    args = parser.parse_args()
    if args.command == "list":
        list_processes()
    elif args.command == "kill":
        kill_process(args.pid)
    elif args.command == "restart":
        restart_process(args.pid, args.exe_path)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
