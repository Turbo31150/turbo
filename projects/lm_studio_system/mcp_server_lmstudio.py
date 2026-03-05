#!/usr/bin/env python3
"""
LM STUDIO MCP SERVER - STANDALONE v1.0
Serveur MCP autonome pour LM Studio avec API HTTP
Fonctionne indépendamment de Claude avec auto-recovery
"""
import json
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configuration paths
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "database" / "lmstudio.db"
CONFIG_PATH = BASE_DIR / "config" / "lmstudio_config.json"
LOG_PATH = BASE_DIR / "logs" / "server.log"

# LM Studio Cluster Configuration
CLUSTER_CONFIG = {
    "M1": {
        "name": "MASTER",
        "url": "http://192.168.1.85:1234",
        "role": "deep_analysis",
        "default_model": "qwen/qwen3-30b-a3b-2507",
        "weight": 1.3,
        "gpu_count": 6,
        "vram_gb": 36,
        "status": "unknown"
    },
    "M2": {
        "name": "DETECTOR",
        "url": "http://192.168.1.26:1234",
        "role": "fast_inference",
        "default_model": "nvidia/nemotron-3-nano",
        "weight": 1.0,
        "gpu_count": 3,
        "vram_gb": 21,
        "status": "unknown"
    },
    "M3": {
        "name": "ORCHESTRATOR",
        "url": "http://192.168.1.113:1234",
        "role": "validation",
        "default_model": "mistralai/mistral-7b-instruct-v0.3",
        "weight": 0.8,
        "gpu_count": 2,
        "vram_gb": 14,
        "status": "unknown"
    },
    "LOCAL": {
        "name": "LOCAL_DEV",
        "url": "http://127.0.0.1:1234",
        "role": "development",
        "default_model": "auto",
        "weight": 0.5,
        "gpu_count": 1,
        "vram_gb": 8,
        "status": "unknown"
    }
}

# MEXC API Configuration
MEXC_API = "https://contract.mexc.com/api/v1/contract/ticker"
MEXC_SPOT_API = "https://www.mexc.com/open/api/v2"

# FastAPI App
app = FastAPI(title="LM Studio MCP Server", version="1.0.0")

# CORS pour accès web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# DATABASE MANAGEMENT
# ============================================

def init_database():
    """Initialize SQLite database with all tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Conversations table (context save)
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        agent_name TEXT,
        role TEXT,
        content TEXT,
        tokens INTEGER,
        model TEXT,
        server TEXT
    )''')

    # Tasks table (agent tasks)
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at REAL,
        agent TEXT,
        task_type TEXT,
        description TEXT,
        status TEXT,
        result TEXT,
        duration_ms INTEGER
    )''')

    # Server health table
    c.execute('''CREATE TABLE IF NOT EXISTS server_health (
        timestamp REAL,
        server_key TEXT,
        status TEXT,
        latency_ms INTEGER,
        error TEXT
    )''')

    # Cache table
    c.execute('''CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value TEXT,
        timestamp REAL,
        ttl INTEGER
    )''')

    # Alerts table
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        alert_type TEXT,
        severity TEXT,
        message TEXT,
        resolved INTEGER DEFAULT 0
    )''')

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {DB_PATH}")

# ============================================
# LOGGING SYSTEM
# ============================================

def log(level: str, message: str, data: Dict = None):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"

    if data:
        log_entry += f" | Data: {json.dumps(data, ensure_ascii=False)}"

    print(log_entry)

    # Write to file
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")

# ============================================
# CLUSTER HEALTH MANAGEMENT
# ============================================

def check_server_health(server_key: str) -> Dict:
    """Check health of single LM Studio server"""
    server = CLUSTER_CONFIG.get(server_key)
    if not server:
        return {"online": False, "error": "Unknown server"}

    start = time.time()
    try:
        url = f"{server['url']}/v1/models"
        req = urllib.request.Request(url, headers={"User-Agent": "LMStudio-MCP/1.0"})

        with urllib.request.urlopen(req, timeout=5) as response:
            latency = int((time.time() - start) * 1000)
            data = json.loads(response.read())

            # Save to DB
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO server_health VALUES (?, ?, ?, ?, ?)",
                     (time.time(), server_key, "online", latency, None))
            conn.commit()
            conn.close()

            CLUSTER_CONFIG[server_key]["status"] = "online"

            return {
                "online": True,
                "latency_ms": latency,
                "models_count": len(data.get("data", [])),
                "name": server["name"]
            }
    except Exception as e:
        error_msg = str(e)

        # Save error to DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO server_health VALUES (?, ?, ?, ?, ?)",
                 (time.time(), server_key, "offline", 0, error_msg))
        conn.commit()
        conn.close()

        CLUSTER_CONFIG[server_key]["status"] = "offline"

        return {
            "online": False,
            "error": error_msg,
            "name": server["name"]
        }

@app.get("/health/cluster")
def cluster_health():
    """Check health of all cluster servers"""
    results = {}
    online_count = 0

    for server_key in ["M1", "M2", "M3", "LOCAL"]:
        health = check_server_health(server_key)
        results[server_key] = health
        if health.get("online"):
            online_count += 1

    status = "HEALTHY" if online_count >= 2 else "DEGRADED" if online_count == 1 else "OFFLINE"

    log("INFO", f"Cluster health check: {status}", {"online": online_count, "total": 4})

    return {
        "status": status,
        "online_count": online_count,
        "total_servers": 4,
        "servers": results,
        "timestamp": time.time()
    }

# ============================================
# LM STUDIO QUERY
# ============================================

def query_lmstudio(server_key: str, prompt: str, max_tokens: int = 500,
                   temperature: float = 0.7, model: str = None) -> Dict:
    """Query specific LM Studio server"""
    server = CLUSTER_CONFIG.get(server_key)
    if not server:
        return {"success": False, "error": f"Unknown server: {server_key}"}

    # Check if server is online
    if server.get("status") == "offline":
        return {"success": False, "error": f"Server {server_key} is offline"}

    url = f"{server['url']}/v1/chat/completions"

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False
    }

    if model:
        payload["model"] = model

    start = time.time()

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read())
            latency = int((time.time() - start) * 1000)

            answer = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            model_used = data.get("model", server["default_model"])

            # Save to conversations DB
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO conversations VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)",
                     (time.time(), server["name"], "assistant", answer, tokens, model_used, server_key))
            conn.commit()
            conn.close()

            return {
                "success": True,
                "answer": answer,
                "server": server_key,
                "server_name": server["name"],
                "model": model_used,
                "latency_ms": latency,
                "tokens": tokens
            }
    except Exception as e:
        error_msg = str(e)
        log("ERROR", f"Query failed for {server_key}", {"error": error_msg, "prompt": prompt[:100]})

        # Create alert
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO alerts VALUES (NULL, ?, ?, ?, ?, 0)",
                 (time.time(), "query_failed", "ERROR", f"Server {server_key}: {error_msg}"))
        conn.commit()
        conn.close()

        return {
            "success": False,
            "error": error_msg,
            "server": server_key
        }

@app.post("/query")
def query_endpoint(data: Dict):
    """Query LM Studio server via API"""
    server_key = data.get("server", "M1")
    prompt = data.get("prompt")
    max_tokens = data.get("max_tokens", 500)
    temperature = data.get("temperature", 0.7)
    model = data.get("model")

    if not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt' parameter")

    result = query_lmstudio(server_key, prompt, max_tokens, temperature, model)
    return result

# ============================================
# AUTO-ROUTING (SMART QUERY)
# ============================================

@app.post("/query/auto")
def auto_query(data: Dict):
    """Auto-route query to best available server"""
    prompt = data.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing 'prompt' parameter")

    # Priority: M1 > M3 > M2 > LOCAL
    priority = ["M1", "M3", "M2", "LOCAL"]

    for server_key in priority:
        if CLUSTER_CONFIG[server_key].get("status") == "online":
            log("INFO", f"Auto-routing to {server_key}", {"prompt": prompt[:50]})
            return query_lmstudio(server_key, prompt,
                                 data.get("max_tokens", 500),
                                 data.get("temperature", 0.7))

    # All servers offline
    log("ERROR", "All servers offline - auto-routing failed")
    return {"success": False, "error": "All cluster servers are offline"}

# ============================================
# WEIGHTED CONSENSUS
# ============================================

@app.post("/consensus")
def weighted_consensus(data: Dict):
    """Get weighted consensus from multiple servers"""
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question' parameter")

    servers_to_query = data.get("servers", ["M1", "M2", "M3"])

    results = {}
    verdicts = {}

    for server_key in servers_to_query:
        if CLUSTER_CONFIG[server_key].get("status") != "online":
            continue

        result = query_lmstudio(server_key, question, max_tokens=100, temperature=0.3)

        if result.get("success"):
            answer = result["answer"].strip().upper()

            # Extract verdict (LONG, SHORT, HOLD)
            verdict = "HOLD"
            if "LONG" in answer:
                verdict = "LONG"
            elif "SHORT" in answer:
                verdict = "SHORT"

            weight = CLUSTER_CONFIG[server_key]["weight"]

            verdicts[server_key] = {
                "verdict": verdict,
                "weight": weight,
                "latency_ms": result["latency_ms"]
            }

            results[server_key] = result

    # Calculate weighted votes
    weighted_votes = {}
    for server_key, data in verdicts.items():
        verdict = data["verdict"]
        weight = data["weight"]
        weighted_votes[verdict] = weighted_votes.get(verdict, 0) + weight

    # Determine consensus
    if weighted_votes:
        consensus = max(weighted_votes, key=weighted_votes.get)
        max_vote = weighted_votes[consensus]
        total_votes = sum(weighted_votes.values())
        confidence = int((max_vote / total_votes) * 100)
    else:
        consensus = "UNKNOWN"
        confidence = 0

    return {
        "success": True,
        "consensus": consensus,
        "confidence": confidence,
        "weighted_votes": weighted_votes,
        "verdicts": verdicts,
        "ia_count": len(verdicts),
        "timestamp": time.time()
    }

# ============================================
# CONTEXT MANAGEMENT
# ============================================

@app.get("/context/save")
def save_context(session_id: str = "default"):
    """Save current conversation context"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get last 50 messages
    c.execute("""SELECT agent_name, role, content, model, server, timestamp
                 FROM conversations
                 ORDER BY id DESC LIMIT 50""")

    messages = []
    for row in c.fetchall():
        messages.append({
            "agent": row[0],
            "role": row[1],
            "content": row[2],
            "model": row[3],
            "server": row[4],
            "timestamp": row[5]
        })

    conn.close()

    # Save to file
    context_file = BASE_DIR / "config" / f"context_{session_id}.json"
    with open(context_file, "w", encoding="utf-8") as f:
        json.dump({
            "session_id": session_id,
            "saved_at": time.time(),
            "messages": list(reversed(messages))
        }, f, indent=2, ensure_ascii=False)

    log("INFO", f"Context saved: {session_id}", {"messages_count": len(messages)})

    return {
        "success": True,
        "session_id": session_id,
        "messages_saved": len(messages),
        "file": str(context_file)
    }

@app.get("/context/restore")
def restore_context(session_id: str = "default"):
    """Restore conversation context"""
    context_file = BASE_DIR / "config" / f"context_{session_id}.json"

    if not context_file.exists():
        return {"success": False, "error": "Context file not found"}

    with open(context_file, "r", encoding="utf-8") as f:
        context = json.load(f)

    log("INFO", f"Context restored: {session_id}", {"messages_count": len(context["messages"])})

    return {
        "success": True,
        "session_id": session_id,
        "saved_at": context["saved_at"],
        "messages": context["messages"]
    }

# ============================================
# MEXC SCANNER
# ============================================

@app.get("/mexc/scan")
def scan_mexc(min_score: int = 75):
    """Scan MEXC for breakout signals"""
    try:
        with urllib.request.urlopen(MEXC_API, timeout=15) as response:
            data = json.loads(response.read())

        tickers = data.get("data", [])
        signals = []

        for t in tickers:
            if not t.get("symbol", "").endswith("_USDT"):
                continue

            symbol = t["symbol"].replace("_USDT", "/USDT")
            price = float(t.get("lastPrice", 0))
            high24 = float(t.get("high24Price", price))
            low24 = float(t.get("low24Price", price))
            change = float(t.get("riseFallRate", 0))
            volume = float(t.get("amount24", 0))

            range_24h = high24 - low24
            if range_24h == 0:
                continue

            position = (price - low24) / range_24h

            # Scoring
            score = 50
            if volume > 10000000:
                score += 15
            elif volume > 5000000:
                score += 10

            if position > 0.90:
                score += 20
            elif position > 0.85:
                score += 15
            elif position < 0.10:
                score += 20
            elif position < 0.15:
                score += 15

            if abs(change) > 20:
                score += 20
            elif abs(change) > 10:
                score += 15
            elif abs(change) > 5:
                score += 10

            if score >= min_score:
                signals.append({
                    "symbol": symbol,
                    "price": price,
                    "change": change,
                    "volume": volume,
                    "position": round(position * 100, 1),
                    "score": score
                })

        signals.sort(key=lambda x: x["score"], reverse=True)

        return {
            "success": True,
            "total_scanned": len(tickers),
            "signals_found": len(signals),
            "min_score": min_score,
            "signals": signals[:20],
            "timestamp": time.time()
        }
    except Exception as e:
        log("ERROR", "MEXC scan failed", {"error": str(e)})
        return {"success": False, "error": str(e)}

# ============================================
# STARTUP & SHUTDOWN
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("=" * 70)
    print("LM STUDIO MCP SERVER v1.0 - STARTING")
    print("=" * 70)

    # Init DB
    init_database()

    # Check cluster health
    health = cluster_health()
    print(f"\nCluster Status: {health['status']}")
    print(f"Online Servers: {health['online_count']}/{health['total_servers']}")

    for server_key, server_health in health["servers"].items():
        status = "ONLINE" if server_health.get("online") else "OFFLINE"
        print(f"  - {server_key} ({server_health['name']}): {status}")

    print("\n" + "=" * 70)
    print("SERVER READY")
    print("API Docs: http://127.0.0.1:8000/docs")
    print("=" * 70 + "\n")

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
