import os
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class JarvisTools:
    def __init__(self, project_dir):
        self.project_dir = Path(project_dir)

    def get_tool_schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Lit le contenu d'un fichier spécifié.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Écrit du contenu dans un fichier.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Exécute une commande shell et retourne le résultat.",
                    "parameters": {
                        "type": "object",
                        "properties": {"cmd": {"type": "string"}},
                        "required": ["cmd"]
                    }
                }
            }
        ]

    def execute_tool(self, name, args):
        if name == "read_file":
            return self.read_file(args.get("path"))
        elif name == "write_file":
            return self.write_file(args.get("path"), args.get("content"))
        elif name == "run_command":
            return self.run_command(args.get("cmd"))
        return f"Tool {name} non reconnu."

    def read_file(self, path):
        target = self.project_dir / path if not path.startswith("/") else Path(path)
        try:
            with open(target, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(self, path, content):
        target = self.project_dir / path if not path.startswith("/") else Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return "File updated successfully."
        except Exception as e:
            return f"Error writing file: {e}"

    def run_command(self, cmd):
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(self.project_dir))
            return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        except Exception as e:
            return f"Command execution failed: {e}"