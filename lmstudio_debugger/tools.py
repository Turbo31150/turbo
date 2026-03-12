#!/usr/bin/env python3
"""
LM STUDIO TOOLS - Module d'appel d'outils pour l'Agent LM Studio M2
API compatible avec OpenAI / LM Studio
"""

import requests
from typing import Any, Dict, List, Optional


class LMStudioTools:
    """Interface pour appeler les outils LM Studio"""

    def __init__(self, base_url: str = "http://127.0.0.1:1234", model: str = "qwen2.5-32b-instruct"):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_endpoint = f"{self.base_url}/v1/chat/completions"

    def call(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 8192) -> Dict[str, Any]:
        """Appeler le modèle LM Studio"""
        
        payload = {
            "model": self.model,
            "messages": [],
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "stream": False
        }

        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})
        
        payload["messages"].append({"role": "user", "content": prompt})

        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                timeout=300  # 5 minutes for complex analysis
            )
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.ConnectionError as e:
            print(f"❌ LM Studio non accessible à {self.base_url}")
            print(f"   Erreur: {e}")
            return {"error": "lm_studio_unavailable", "details": str(e)}
        
        except Exception as e:
            print(f"❌ Erreur appel API LM Studio: {e}")
            return {"error": "api_call_failed", "details": str(e)}

    def analyze_code(self, file_path: str, context: str = "") -> Dict[str, Any]:
        """Analyser un fichier de code avec le modèle"""
        
        system_prompt = """Tu es un expert en analyse de code Python. Ta mission est d'identifier les bugs, les problèmes de sécurité, et les opportunités d'amélioration."""

        prompt = f"Analyse ce fichier: {file_path}\n\nContexte: {context}\n\nIdentifie tous les problèmes potentiels (bugs, security issues, code smell) et propose des corrections."
        
        return self.call(prompt, system_prompt=system_prompt)

    def generate_fix(self, file_path: str, issue_description: str, current_code: str) -> Dict[str, Any]:
        """Générer un correctif pour une issue"""
        
        system_prompt = """Tu es un expert développeur Python. Ta mission est de générer des corrections précises et testées pour les bugs identifiés dans le code."""

        prompt = f"Fichier: {file_path}\n\nProblème: {issue_description}\n\nCode actuel:\n```python\n{current_code}\n```\n\nGénère une correction complète qui résout ce problème sans introduire de régressions."
        
        return self.call(prompt, system_prompt=system_prompt)

    def test_function(self, code_snippet: str, test_cases: List[Dict]) -> Dict[str, Any]:
        """Tester un snippet de code avec des cas de test"""
        
        system_prompt = "Tu es un expert en tests unitaires. Génère des tests complets pour valider la fonctionnalité."

        prompt = f"Code à tester:\n```python\n{code_snippet}\n```\n\nCas de test attendus: {test_cases}\n\nGénère une suite de tests complète et valide les résultats."
        
        return self.call(prompt, system_prompt=system_prompt)


# Tools MCP pour le Flask server (alternative to LM Studio API calls)
MCP_TOOLS = [
    {
        "name": "read_file",
        "description": "Lire le contenu d'un fichier",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin absolu du fichier"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Écrire du contenu dans un fichier",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_command",
        "description": "Exécuter une commande shell",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "analyze_logs",
        "description": "Analyser les logs pour trouver des erreurs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "log_path": {"type": "string"},
                "pattern": {"type": "string"}
            },
            "required": ["log_path"]
        }
    },
    {
        "name": "deploy_cluster",
        "description": "Déployer/Redémarrer le cluster JARVIS M1",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["restart", "status", "health_check"]}
            },
            "required": ["action"]
        }
    }
]
