import os
import sys
import json
import time
import logging
import requests
from tools import JarvisTools

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

def query_lm_studio(config, messages, tools=None):
    url = f"{config['lm_studio_url']}/chat/completions"
    payload = {
        "model": config['model'],
        "messages": messages,
        "temperature": 0.3,
    }
    if tools:
        payload["tools"] = tools
        
    for attempt in range(config.get("max_retries", 5)):
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"LM Studio API failed (attempt {attempt+1}): {e}")
            time.sleep(5)
    
    # Fallback to Ollama
    logger.error("Switching to Ollama fallback...")
    url = f"{config['ollama_fallback_url']}/chat/completions"
    payload["model"] = config["ollama_fallback_model"]
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ollama fallback failed: {e}")
        return None

def main_loop():
    config = load_config()
    jarvis_tools = JarvisTools(config['project_dir'])
    
    system_prompt = """Tu es JARVIS Auto-Debugger. Ton rôle est d'analyser les logs, trouver les erreurs et proposer/appliquer des correctifs automatiquement sur les scripts Python et services systemd. Utilise les outils à ta disposition pour lire/écrire des fichiers et exécuter des tests."""
    
    while True:
        logger.info("--- Starting new Auto-Debug Cycle ---")
        # 1. Obtenir l'état du système (ex: systemctl failed)
        status_check = jarvis_tools.run_command("systemctl --user --failed --no-pager")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyse cet état système et effectue les corrections nécessaires via les outils. État:\n{status_check}"}
        ]
        
        response = query_lm_studio(config, messages, tools=jarvis_tools.get_tool_schemas())
        
        if response and "choices" in response:
            message = response["choices"][0]["message"]
            
            # Gestion du Tool Calling
            if message.get("tool_calls"):
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    args = json.loads(tool_call["function"]["arguments"])
                    logger.info(f"Executing tool: {func_name} with {args}")
                    
                    result = jarvis_tools.execute_tool(func_name, args)
                    logger.info(f"Tool result: {result[:200]}...") # Truncated log
            else:
                logger.info(f"Agent response: {message.get('content')}")
        
        logger.info(f"Cycle finished. Sleeping for {config['scan_interval_seconds']} seconds.")
        time.sleep(config['scan_interval_seconds'])

if __name__ == "__main__":
    main_loop()