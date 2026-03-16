"""JARVIS OpenClaw Gateway v2 — Optimized Linux Native Server.
Supports streaming, agent metadata, and advanced routing.
"""
import logging
import uvicorn
import json
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from src.openclaw_bridge import get_bridge
from pathlib import Path

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [OPENCLAW] %(message)s")
logger = logging.getLogger("jarvis.openclaw_gateway")

app = FastAPI(title="JARVIS OpenClaw Gateway v2")
bridge = get_bridge()

# Load agent metadata
CONFIG_PATH = Path("/home/turbo/jarvis/data/openclaw_40agents.json")
agents_data = {}
if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            agents_data = {a['id']: a for a in config.get('agents', [])}
    except Exception as e:
        logger.error(f"Failed to load agent metadata: {e}")

@app.get("/")
@app.get("/health")
async def health():
    return {
        "status": "ok", 
        "service": "openclaw-gateway", 
        "version": "2.0.0-linux",
        "agents_loaded": len(agents_data)
    }

@app.post("/v1/chat/completions")
@app.post("/chat")
async def chat_endpoint(request: Request):
    try:
        body = await request.json()
        stream = body.get("stream", False)
        message = body.get("message", body.get("prompt", ""))
        
        if not message and "messages" in body:
            message = body["messages"][-1]["content"]
            
        # Intent classification & routing
        result = bridge.route(message)
        agent_id = result.agent_id if hasattr(result, 'agent_id') else "unknown"
        
        logger.info(f"Route: [{agent_id}] -> {message[:60]}...")

        # For now, OpenClaw Bridge returns final text. 
        # We wrap it in an OpenAI-compatible format.
        content = result.content if hasattr(result, 'content') else str(result)
        
        response_data = {
            "id": f"ocw-{os.getpid()}-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": agent_id,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        
        return JSONResponse(content=response_data)
    except Exception as e:
        logger.error(f"Gateway error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import time
    logger.info(f"Launching OpenClaw v2 on port 18789 with {len(agents_data)} agents metadata...")
    uvicorn.run(app, host="127.0.0.1", port=18789, log_level="warning")
