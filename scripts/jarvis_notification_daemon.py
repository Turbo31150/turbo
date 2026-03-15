"""Daemon de notifications JARVIS — surveille GPU, services, et alertes."""
import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("jarvis.notif")

ICON = "/home/turbo/Pictures/JARVIS/jarvis-icon-48.png"
CHECK_INTERVAL = 30  # secondes
GPU_WARN = 75
GPU_CRIT = 85

def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return r.stdout.strip()
    except: return ""

def _notify(title, msg, urgency="normal"):
    subprocess.Popen(["notify-send", "-i", ICON, "-u", urgency, "-a", "JARVIS OS", title, msg],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def check_gpu():
    output = _run(["nvidia-smi", "--query-gpu=index,temperature.gpu", "--format=csv,noheader,nounits"])
    for line in output.split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            idx, temp = parts[0], int(parts[1])
            if temp >= GPU_CRIT:
                _notify("ALERTE GPU", f"GPU{idx} a {temp}°C ! Risque de throttling", "critical")
                logger.warning("GPU%s CRITICAL: %d°C", idx, temp)
            elif temp >= GPU_WARN:
                _notify("GPU Chaud", f"GPU{idx} a {temp}°C", "normal")

def check_services():
    output = _run("systemctl --user list-units 'jarvis-*' --state=failed --no-pager --no-legend")
    if output.strip():
        failed = [l.split()[0].replace(".service", "") for l in output.strip().split("\n")]
        _notify("Service JARVIS en erreur", "\n".join(failed), "critical")
        logger.warning("Services failed: %s", failed)

def check_disk():
    output = _run(["df", "/", "--output=pcent"])
    for line in output.split("\n"):
        line = line.strip().rstrip("%")
        if line.isdigit() and int(line) > 90:
            _notify("Disque presque plein", f"Usage: {line}%", "critical")

def main():
    logger.info("JARVIS Notification Daemon démarré (interval=%ds)", CHECK_INTERVAL)
    while True:
        try:
            check_gpu()
            check_services()
            check_disk()
        except Exception as e:
            logger.error("Erreur check: %s", e)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
