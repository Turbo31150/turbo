"""LM Studio Guard — Ensures M1 node API is always responsive.
Restarts the lms server if port 1234 is unresponsive.
"""
import socket
import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [LMS-GUARD] %(message)s")
logger = logging.getLogger("jarvis.lms_guard")

LMS_BIN = "/home/turbo/.lmstudio/bin/lms"

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def restart_lms():
    logger.warning("LM Studio API (1234) is DOWN. Attempting restart...")
    subprocess.run([LMS_BIN, "server", "stop"], capture_output=True)
    time.sleep(2)
    subprocess.Popen([LMS_BIN, "server", "start", "--port", "1234"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(10)
    if check_port(1234):
        logger.info("LM Studio API successfully recovered.")
    else:
        logger.error("Failed to recover LM Studio API.")

if __name__ == "__main__":
    logger.info("LM Studio Health Guard active.")
    while True:
        if not check_port(1234):
            restart_lms()
        time.sleep(60)
