#!/usr/bin/env python3
"""JARVIS Command Guard - Whitelist & Confirmation."""

import sys
import os

WHITELIST = ["ls", "nvidia-smi", "systemctl status", "python3 main.py -s", "date", "whoami"]
BLACKLIST = ["rm -rf", "format", "sudo su", ":(){ :|:& };:"]

def validate_command(cmd: str):
    cmd = cmd.lower().strip()
    
    # Check blacklist
    for bad in BLACKLIST:
        if bad in cmd:
            return False, "⚠️ Commande INTERDITE détectée (Blacklist)."
            
    # Check whitelist (starts with)
    allowed = False
    for good in WHITELIST:
        if cmd.startswith(good):
            allowed = True
            break
            
    if not allowed:
        return False, f"⚠️ Commande '{cmd}' non whitelistée. Confirmation requise."
        
    return True, "OK"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        ok, msg = validate_command(cmd)
        if not ok:
            print(msg)
            sys.exit(1)
        else:
            print("Commande validée.")
            sys.exit(0)
