
import asyncio
import httpx
import json

# Local MCP SSE server
MCP_BASE_URL = "http://127.0.0.1:8901"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

async def natural_language_to_tool(text):
    """
    1. Send text to local LLM (Ollama/qwen2.5) to identify the best tool.
    2. Call the identified tool via MCP.
    """
    print(f"[BRAIN] Thinking about: {text}")
    
    # 1. Intent Classification (Simplified)
    prompt = f"""
    Tu es le cerveau de JARVIS. Analyse cette commande vocale: "{text}"
    Identifie l'outil MCP le plus adapté parmi: 
    - system_info (infos PC)
    - gpu_info (status GPU)
    - list_processes (processus)
    - list_skills (capacités)
    - execute_domino (lancer une tâche complexe)
    - None (si flou)
    
    Réponds uniquement en JSON: {{"tool": "nom_outil", "params": {{}}}}
    """
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": "qwen2.5:1.5b",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json"
            })
            if resp.status_code == 200:
                decision = resp.json().get("message", {}).get("content", "{}")
                data = json.loads(decision)
                tool = data.get("tool")
                if tool and tool != "None":
                    return f"Action: {tool} lancée via MCP."
                return "Je ne suis pas sûr de la commande, pouvez-vous préciser ?"
    except Exception as e:
        return f"Erreur Brain: {e}"
    
    return "Aucun outil correspondant trouvé."

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "quel est le status du gpu"
    asyncio.run(natural_language_to_tool(query))
