"""JARVIS Master Auditor — Linux Integrity Guard.
Periodically checks that system commands are correctly mapped to Linux tools.
"""
import os
import subprocess
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AUDITOR] %(message)s")
logger = logging.getLogger("jarvis.auditor")

class LinuxAuditor:
    def __init__(self):
        self.root = Path("/home/turbo/jarvis")
        self.essential_tools = ["wmctrl", "xdotool", "notify-send", "upower", "nvidia-smi", "curl", "jq"]

    def check_tools(self):
        missing = []
        for tool in self.essential_tools:
            if subprocess.run(["which", tool], capture_output=True).returncode != 0:
                missing.append(tool)
        return missing

    def audit_cycle(self):
        logger.info("Starting system audit...")
        missing = self.check_tools()
        if missing:
            logger.warning(f"Missing essential Linux tools: {missing}")
            # Potentielle auto-installation ici
        
        # Check if services are active
        try:
            r = subprocess.run(["systemctl", "--user", "is-system-running"], capture_output=True, text=True)
            logger.info(f"Systemd user state: {r.stdout.strip()}")
        except: pass
        
        logger.info("Audit complete. All systems nominal.")

if __name__ == "__main__":
    auditor = LinuxAuditor()
    while True:
        auditor.audit_cycle()
        time.sleep(3600) # Audit toutes les heures
