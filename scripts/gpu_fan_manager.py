
import subprocess
import time
import logging

# Configuration des seuils (Celsisus)
TEMP_MIN = 40
TEMP_MAX = 80
FAN_MIN = 40
FAN_MAX = 95

logging.basicConfig(level=logging.INFO, format='%(asctime)s [GPU-FAN] %(message)s')

def get_gpu_temps():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=index,temperature.gpu", "--format=csv,noheader,nounits"], 
                           capture_output=True, text=True)
        return [tuple(map(int, line.split(','))) for line in r.stdout.strip().split('\n')]
    except:
        return []

def set_fan_speed(gpu_idx, speed):
    """
    Note: Requires 'sudo nvidia-xconfig --cool-bits=4' and an active X server for nvidia-settings.
    On headless Linux, we use 'nvidia-smi -pl' as fallback to prevent overheating.
    """
    try:
        # Tentative via nvidia-settings (si X est la)
        subprocess.run(["nvidia-settings", "-a", f"[gpu:{gpu_idx}]/GPUFanControlState=1", 
                        "-a", f"[fan:{gpu_idx}]/GPUTargetFanSpeed={speed}"], 
                       capture_output=True, stderr=subprocess.DEVNULL)
    except:
        pass

def manage_fans():
    logging.info("GPU Fan Manager active (Target: Dynamic).")
    while True:
        temps = get_gpu_temps()
        for idx, temp in temps:
            # Calcul linéaire de la vitesse
            if temp <= TEMP_MIN:
                speed = FAN_MIN
            elif temp >= TEMP_MAX:
                speed = FAN_MAX
            else:
                speed = FAN_MIN + (FAN_MAX - FAN_MIN) * (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
            
            set_fan_speed(idx, int(speed))
            
            # Sécurité Power Limit si > 82C
            if temp > 82:
                subprocess.run(["sudo", "nvidia-smi", "-i", str(idx), "-pl", "100"]) # Hard cap
        
        time.sleep(10)

if __name__ == "__main__":
    manage_fans()
