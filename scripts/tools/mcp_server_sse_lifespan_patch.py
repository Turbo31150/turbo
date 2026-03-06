"""Patch pour mcp_server_sse.py - Nouveau lifespan avec bootstrap JARVIS.

Remplace le lifespan actuel ligne ~352 par ce code ameliore.

Instructions:
    1. Ouvrir F:\\BUREAU\\turbo\\src\\mcp_server_sse.py
    2. Trouver la fonction lifespan (ligne ~352)
    3. Remplacer le @contextlib.asynccontextmanager + fonction par le code ci-dessous
"""

import contextlib
from collections.abc import AsyncIterator
from starlette.applications import Starlette

# Code a inserer:

@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Lifespan avec bootstrap JARVIS complet."""
    import logging
    logger = logging.getLogger("jarvis.mcp_remote")
    
    # STARTUP
    logger.info("Starting StreamableHTTP session manager...")
    async with session_manager.run():
        logger.info("StreamableHTTP session manager started")
        
        # Bootstrap JARVIS
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
                    f"JARVIS Bootstrap partial ({result.get('steps_ok')}/{result.get('steps_total')} steps OK) "
                    f"- Errors: {result.get('errors')}"
                )
        except Exception as e:
            logger.error(f"JARVIS Bootstrap FAILED: {e}", exc_info=True)
        
        logger.info("JARVIS MCP Server READY - All systems operational")
        
        yield
    
    # SHUTDOWN
    logger.info("Shutting down JARVIS...")
    try:
        from src.startup_wiring import shutdown_jarvis
        result = await shutdown_jarvis()
        logger.info(f"JARVIS Shutdown complete in {result.get('duration_ms')}ms")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

