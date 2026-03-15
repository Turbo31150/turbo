
import subprocess
import time
import os
import socket
import logging

# Configuration Resilience Max
PORTS = {8901: "jarvis-mcp", 9742: "jarvis-ws", 18800: "jarvis-proxy", 11434: "ollama"}
CHECK_INTERVAL = 60

logging.basicConfig(level=logging.INFO, format='%(asctime)s [UNSTOPPABLE-HEAL] %(message)s')

def run_cmd(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, shell=isinstance(cmd, str))
    except Exception as e:
        return None

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def fix_port(port, service):
    logging.warning(f"Port {port} ({service}) is DOWN. Fixing...")
    # 1. Kill owner
    r = run_cmd(f"lsof -t -i:{port}")
    if r and r.stdout:
        for pid in r.stdout.strip().split("\n"):
            logging.info(f"Killing port owner PID {pid}")
            run_cmd(["kill", "-9", pid])
    
    # 2. Restart via systemd
    unit = f"{service}.service"
    cmd = ["systemctl", "--user", "restart", unit] if service.startswith("jarvis") else ["sudo", "systemctl", "restart", service]
    run_cmd(cmd)

def check_nvidia():
    r = run_cmd(["nvidia-smi"])
    if not r or r.returncode != 0:
        logging.error("NVIDIA-SMI failed! Attempting driver recovery...")
        run_cmd(["sudo", "nvidia-persistenced"])
        run_cmd(["sudo", "modprobe", "nvidia"])

def check_docker():
    r = run_cmd(["docker", "ps"])
    if not r or r.returncode != 0:
        logging.error("Docker not responding. Restarting engine...")
        run_cmd(["sudo", "systemctl", "restart", "docker"])

def check_zram():
    r = run_cmd(["zramctl"])
    if not r or "/dev/zram0" not in r.stdout:
        logging.warning("ZRAM not active. Re-applying boot optimization...")
        run_cmd(["sudo", "/home/turbo/jarvis/scripts/jarvis-optimize-boot.sh"])

def main_loop():
    logging.info("Resilience Protocol Active (YOLO Mode)")
    while True:
        try:
            # Check Ports
            for port, service in PORTS.items():
                if not is_port_open(port):
                    fix_port(port, service)
            
            # Check Critical Systems
            check_nvidia()
            check_docker()
            check_zram()
            
            # Checkpoint (simulé)
            with open(os.path.expanduser("~/.gemini/checkpoints/auto_heal_pulse.json"), "w") as f:
                f.write(f'{{"last_check": {time.time()}, "status": "healthy"}}')

        except Exception as e:
            logging.error(f"Heal loop error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main_loop()
