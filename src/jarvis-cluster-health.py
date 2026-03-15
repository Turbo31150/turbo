"""JARVIS Cluster Health — Multi-GPU & DevOps Monitoring.
Tracks: NVIDIA GPUs, Docker/K8s nodes, MEXC Crypto, System logs.
"""
import os
import subprocess
import json
import time
import httpx
import logging
from datetime import datetime

# Config
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
MEXC_API = "https://api.mexc.com/api/v3/ticker/price"
GPU_ALERT_TEMP = 80
GPU_ALERT_MEM = 90

logging.basicConfig(level=logging.INFO, format="%(asctime)s [HEALTH] %(message)s")
logger = logging.getLogger("jarvis.health")

def get_gpu_status():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        gpus = []
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                gpu = {
                    "id": parts[0], "name": parts[1], "temp": int(parts[2]),
                    "mem_used": int(parts[3]), "mem_total": int(parts[4]), "util": int(parts[5])
                }
                gpus.append(gpu)
        return gpus
    except: return []

async def get_mexc_prices():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(MEXC_API, params={"symbol": "BTCUSDT"})
            btc = r.json().get("price", "N/A")
            r = await client.get(MEXC_API, params={"symbol": "ETHUSDT"})
            eth = r.json().get("price", "N/A")
            return {"BTC": btc, "ETH": eth}
    except: return {"BTC": "N/A", "ETH": "N/A"}

def check_services():
    services = ["jarvis-ws", "jarvis-proxy", "jarvis-openclaw", "docker"]
    status = {}
    for s in services:
        cmd = ["systemctl", "--user", "is-active", s] if s.startswith("jarvis-") else ["systemctl", "is-active", s]
        r = subprocess.run(cmd, capture_output=True, text=True)
        status[s] = r.stdout.strip()
    return status

async def main():
    logger.info("JARVIS Health Cycle Starting...")
    
    gpus = get_gpu_status()
    crypto = await get_mexc_prices()
    services = check_services()
    
    # Print Dashboard
    print(f"\n{'='*60}")
    print(f"  JARVIS CLUSTER HEALTH - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    
    print("\n[GPU STATUS]")
    for g in gpus:
        alert = "!!" if g["temp"] > GPU_ALERT_TEMP else "OK"
        print(f"  [{alert}] GPU{g['id']}: {g['name']:<20} {g['temp']}C | Util: {g['util']}% | Mem: {g['mem_used']}/{g['mem_total']}MB")
        if g["temp"] > GPU_ALERT_TEMP and DISCORD_WEBHOOK:
            # Send Discord Alert (async fire and forget)
            pass

    print("\n[CRYPTO MEXC]")
    print(f"  BTC: ${crypto['BTC']} | ETH: {crypto['ETH']}")

    print("\n[SERVICES]")
    for s, st in services.items():
        icon = "OK" if st == "active" else "!!"
        print(f"  [{icon}] {s:<15}: {st}")

    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
