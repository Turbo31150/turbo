
import asyncio
import time
from pathlib import Path
import os

# Import pipeline
import sys
sys.path.append("/home/turbo/jarvis")
from src.voice_pipeline_v3 import JarvisVoiceV3

async def stress_test():
    print("=== JARVIS VOICE STRESS TEST ===")
    pipeline = JarvisVoiceV3()
    
    t0 = time.monotonic()
    # 1. Simulate TTS latency
    print("Testing TTS (Piper)...")
    await pipeline.speak("Test de latence vocale Jarvis")
    t1 = time.monotonic()
    print(f"TTS Latency: {t1-t0:.3f}s")
    
    # 2. Simulate Dispatch latency
    print("\nTesting Command Dispatch (MCP)...")
    t2 = time.monotonic()
    resp = await pipeline.dispatch_command("quelle heure est-il")
    t3 = time.monotonic()
    print(f"MCP Response: {resp}")
    print(f"Dispatch Latency: {t3-t2:.3f}s")
    
    print(f"\nTOTAL PIPELINE LATENCY: {t3-t0:.3f}s")

if __name__ == "__main__":
    asyncio.run(stress_test())
