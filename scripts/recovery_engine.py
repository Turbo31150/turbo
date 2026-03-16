
import subprocess
import os
import sys
import re
import time
import logging

# Configuration de la Matrice de Résilience
ERROR_PATRICES = {
    r"ModuleNotFoundError: No module named '([^']+)'": "uv pip install {0}",
    r"ImportError: cannot import name '([^']+)'": "find . -name '*.py' | xargs grep -l {0} # Manual check needed but auto-fix pathing",
    r"command not found: ([^ \n]+)": "sudo apt install -y {0}",
    r"address already in use (?:'127.0.0.1', (\d+)|0.0.0.0:(\d+))": "fuser -k {0}/tcp",
    r"Permission denied": "chmod +x {0}",
    r"NVIDIA-SMI has failed": "sudo nvidia-persistenced && sudo modprobe nvidia",
    r"out of memory": "sudo /home/turbo/jarvis/scripts/jarvis-optimize-boot.sh # Trigger ZRAM reset",
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [RECOVERY-ALGO] %(message)s')

class RecoveryEngine:
    def __init__(self, log_source="jarvis-master.service"):
        self.log_source = log_source

    def get_last_error(self):
        """Extrait la dernière erreur fatale des logs systemd."""
        cmd = f"journalctl --user -u {self.log_source} -n 50 --no-pager"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return r.stdout

    def diagnose_and_fix(self):
        logs = self.get_last_error()
        fixed = False

        for pattern, action_template in ERROR_PATRICES.items():
            match = re.search(pattern, logs)
            if match:
                error_val = match.group(1) if match.groups() else ""
                logging.warning(f"MATCHED PATTERN: {pattern} | VAL: {error_val}")
                
                # Construction de la commande de fix
                fix_cmd = action_template.format(error_val)
                logging.info(f"EXECUTING AUTO-FIX: {fix_cmd}")
                
                try:
                    subprocess.run(fix_cmd, shell=True, check=True)
                    logging.info("✅ Fix applied successfully.")
                    fixed = True
                except Exception as e:
                    logging.error(f"❌ Failed to apply fix: {e}")

        return fixed

    def run_loop(self):
        logging.info(f"Recovery Engine watching {self.log_source}...")
        while True:
            if self.diagnose_and_fix():
                logging.info("System state modified by recovery. Validating...")
                subprocess.run(["systemctl", "--user", "restart", self.log_source])
            time.sleep(30)

if __name__ == "__main__":
    # Watch the master by default
    engine = RecoveryEngine("jarvis-master.service")
    engine.run_loop()
