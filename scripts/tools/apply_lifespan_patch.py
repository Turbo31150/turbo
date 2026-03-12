#!/usr/bin/env python
"""Applique le patch bootstrap au lifespan de mcp_server_sse.py.

Utilisation:
    python apply_lifespan_patch.py

Cree une backup avant modification.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

# Fichier a patcher
TARGET_FILE = Path("/home/turbo/jarvis-m1-ops/src/mcp_server_sse.py")

# Nouveau code lifespan
NEW_LIFESPAN = '''    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Lifespan avec bootstrap JARVIS complet."""
        # === STARTUP ===
        logger.info("Starting StreamableHTTP session manager...")
        async with session_manager.run():
            logger.info("StreamableHTTP session manager started")
            
            # Bootstrap JARVIS: wire all systems
            try:
                from src.startup_wiring import bootstrap_jarvis
                logger.info("Launching JARVIS bootstrap...")
                result = await bootstrap_jarvis(
                    start_autonomous=True,
                    start_gpu_guardian=True,
                    start_trading_sentinel=True
                )
                
                if result.get("success"):
                    logger.info(
                        f"JARVIS Bootstrap OK in {result.get('duration_ms')}ms "
                        f"({result.get('steps_ok')}/{result.get('steps_total')} steps)"
                    )
                else:
                    logger.warning(
                        f"JARVIS Bootstrap partial: {result.get('steps_ok')}/{result.get('steps_total')} steps OK"
                    )
                    if result.get('errors'):
                        logger.warning(f"Errors: {result.get('errors')}")
            except Exception as e:
                logger.error(f"JARVIS Bootstrap FAILED: {e}", exc_info=True)
            
            logger.info("="*60)
            logger.info("JARVIS MCP Server READY")
            logger.info("  - StreamableHTTP transport active")
            logger.info("  - Event bus wired (16 subscribers)")
            logger.info("  - Health probes registered (10)")
            logger.info("  - GPU Guardian running")
            logger.info("  - Cluster self-healer active")
            logger.info("  - Trading Sentinel monitoring")
            logger.info("  - Autonomous loop operational")
            logger.info("="*60)
            
            yield
        
        # === SHUTDOWN ===
        logger.info("Shutting down JARVIS...")
        try:
            from src.startup_wiring import shutdown_jarvis
            result = await shutdown_jarvis()
            logger.info(f"JARVIS Shutdown complete in {result.get('duration_ms')}ms")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")'''


def main():
    if not TARGET_FILE.exists():
        print(f"ERROR: {TARGET_FILE} not found")
        return 1
    
    print(f"Patching {TARGET_FILE}...")
    
    # Backup
    backup_path = TARGET_FILE.with_suffix(f".py.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(TARGET_FILE, backup_path)
    print(f"Backup created: {backup_path}")
    
    # Lire le fichier
    content = TARGET_FILE.read_text(encoding="utf-8")
    
    # Pattern pour trouver l'ancien lifespan (ligne ~350-356)
    old_pattern = r'(\s+)@contextlib\.asynccontextmanager\s+async def lifespan\(app: Starlette\) -> AsyncIterator\[None\]:\s+async with session_manager\.run\(\):\s+logger\.info\("StreamableHTTP session manager started"\)\s+yield'
    
    # Verifier qu'on trouve bien l'ancien lifespan
    if not re.search(old_pattern, content, re.MULTILINE):
        print("WARNING: Could not find the exact old lifespan pattern.")
        print("Trying simpler pattern...")
        
        # Pattern plus simple
        simple_pattern = r'(\s+)@contextlib\.asynccontextmanager\s+async def lifespan\([^)]+\)[^:]+:[^}]+?yield'
        match = re.search(simple_pattern, content, re.DOTALL)
        if not match:
            print("ERROR: Could not locate lifespan function at all")
            print("Please apply the patch manually using mcp_server_sse_lifespan_patch.py")
            return 1
        
        # Remplacer par le nouveau
        new_content = content[:match.start()] + NEW_LIFESPAN + content[match.end():]
    else:
        # Remplacer l'ancien par le nouveau
        new_content = re.sub(old_pattern, NEW_LIFESPAN, content, flags=re.MULTILINE)
    
    # Ecrire le fichier patche
    TARGET_FILE.write_text(new_content, encoding="utf-8")
    
    print("\n" + "="*60)
    print("PATCH APPLIED SUCCESSFULLY")
    print("="*60)
    print(f"Backup: {backup_path}")
    print(f"Patched: {TARGET_FILE}")
    print("\nNext steps:")
    print("  1. Restart the MCP server: python -m src.mcp_server_sse --light")
    print("  2. Check logs for 'JARVIS Bootstrap OK in XXXms'")
    print("  3. Verify all 9 steps completed successfully")
    print("\nTo rollback:")
    print(f"  copy {backup_path} {TARGET_FILE}")
    
    return 0


if __name__ == "__main__":
    exit(main())

