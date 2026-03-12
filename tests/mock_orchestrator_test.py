import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_structure():
    print("--- TEST STRUCTURE JARVIS M1 ---")
    print(f"Project Dir: {os.getenv('PROJECT_DIR', 'Not set')}")
    print(f"GPU Count: {os.getenv('GPU_COUNT', 'Not set')}")
    
    # Simuler un dispatch vers le GPU scheduler
    try:
        from src.gpu_scheduler import allocate_gpu
        idx = allocate_gpu(4000)
        print(f"Success: GPU Scheduler allocated GPU {idx} for 4GB model.")
    except Exception as e:
        print(f"Error: GPU Scheduler failed: {e}")

    # Vérifier l'accès au MCP
    mcp_config = os.path.exists(".mcp.json")
    print(f"MCP Config: {'OK' if mcp_config else 'FAIL'}")
    
    # Vérifier les chemins Linux
    import src.config as cfg
    if "/home/turbo/jarvis-m1-ops" in str(cfg.PATHS["turbo"]):
        print("Success: Linux paths correctly configured in config.py.")
    else:
        print(f"Fail: Path mismatch: {cfg.PATHS['turbo']}")

if __name__ == "__main__":
    asyncio.run(test_structure())
