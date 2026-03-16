
import os
import sys

# Mapping Matériel (index nvidia-smi)
GPU_MAP = {
    "RTX_3080": "5",   # Inférence Lourde (DeepSeek R1)
    "RTX_2060": "0",   # Inférence Moyenne (Qwen 7B)
    "GTX_1660S": "1,2,3,4" # Light tasks / Monitoring / Voice
}

# Profils JARVIS
PROFILES = {
    "HEAVY": GPU_MAP["RTX_3080"],
    "BALANCED": f"{GPU_MAP['RTX_3080']},{GPU_MAP['RTX_2060']}",
    "LIGHT": GPU_MAP["GTX_1660S"],
    "ALL": "0,1,2,3,4,5"
}

def get_cuda_env(profile="LIGHT"):
    devices = PROFILES.get(profile, GPU_MAP["GTX_1660S"])
    return f"CUDA_VISIBLE_DEVICES={devices}"

if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "LIGHT"
    print(get_cuda_env(profile))
