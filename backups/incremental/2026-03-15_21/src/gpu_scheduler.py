#!/usr/bin/env python3
"""JARVIS GPU Scheduler - Routes tasks based on VRAM requirements."""

import subprocess
import sys
import json

def get_gpu_info():
    """Returns a list of GPUs with index, name, and free VRAM in MiB."""
    cmd = "nvidia-smi --query-gpu=index,name,memory.free --format=json"
    try:
        res = subprocess.check_output(cmd.split(), text=True)
        # Handle nvidia-smi json output quirks
        data = json.loads(res)
        return [{"id": int(g["index"]), "name": g["name"], "free": int(g["memory.free"].split()[0])} for g in data["gpus"]]
    except:
        return []

def allocate_gpu(vram_needed_mib: int):
    """Pick the best GPU index for the requested VRAM."""
    gpus = sorted(get_gpu_info(), key=lambda x: x["free"])
    for gpu in gpus:
        if gpu["free"] >= vram_needed_mib:
            return gpu["id"]
    return gpus[-1]["id"] if gpus else 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(allocate_gpu(int(sys.argv[1])))
    else:
        # Default allocation strategy
        print(json.dumps(get_gpu_info(), indent=2))
