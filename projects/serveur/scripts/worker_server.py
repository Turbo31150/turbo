"""
WORKER SERVER - Gestionnaire de Serveur Distribue
Machine: Worker (192.168.1.26 ou 192.168.1.113)
Role: Recevoir et executer les taches du Master
"""

import socket
import json
import threading
import subprocess
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = Path("C:/CLAUDE_WORKSPACE/SERVER_MANAGER")
CONFIG_FILE = BASE_DIR / "config" / "network_config.json"
LOG_DIR = BASE_DIR / "logs"
TASK_DIR = BASE_DIR / "tasks"

class WorkerServer:
    def __init__(self, host='0.0.0.0', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.tasks_queue = []
        self.current_task = None
        self.worker_id = self._detect_worker_id()

        # Charger config
        self.config = self._load_config()

        # Stats
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "uptime_start": None,
            "last_heartbeat": None
        }

    def _detect_worker_id(self):
        """Detecter automatiquement l'ID du worker basé sur l'IP"""
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        if "26" in local_ip or local_ip == "192.168.1.26":
            return "worker1"
        elif "113" in local_ip or local_ip == "192.168.1.113":
            return "worker2"
        return "worker_unknown"

    def _load_config(self):
        """Charger la configuration reseau"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.log(f"ERREUR config: {e}")
            return {}

    def log(self, message, level="INFO"):
        """Logger un message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] [{self.worker_id}] {message}"
        print(log_line)

        # Sauvegarder dans fichier
        log_file = LOG_DIR / f"worker_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + "\n")
        except:
            pass

    def start(self):
        """Demarrer le serveur Worker"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            self.stats["uptime_start"] = datetime.now().isoformat()

            self.log(f"=== WORKER SERVER DEMARRE ===")
            self.log(f"Ecoute sur {self.host}:{self.port}")
            self.log(f"Worker ID: {self.worker_id}")

            # Thread heartbeat vers Master
            heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            heartbeat_thread.start()

            # Boucle principale
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    self.log(f"Connexion de {address}")

                    # Thread pour traiter la connexion
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()

                except Exception as e:
                    if self.running:
                        self.log(f"Erreur accept: {e}", "ERROR")

        except Exception as e:
            self.log(f"Erreur demarrage: {e}", "ERROR")
        finally:
            self.stop()

    def _handle_client(self, client_socket, address):
        """Traiter une connexion client (Master)"""
        try:
            data = client_socket.recv(65536).decode('utf-8')
            if not data:
                return

            request = json.loads(data)
            command = request.get("command", "")

            self.log(f"Commande recue: {command}")

            # Router la commande
            response = self._process_command(request)

            # Envoyer reponse
            client_socket.send(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.log(f"Erreur traitement: {e}", "ERROR")
            error_response = {"status": "error", "message": str(e)}
            try:
                client_socket.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()

    def _process_command(self, request):
        """Traiter une commande du Master"""
        command = request.get("command", "")

        if command == "PING":
            return {
                "status": "ok",
                "response": "PONG",
                "worker_id": self.worker_id,
                "timestamp": datetime.now().isoformat()
            }

        elif command == "STATUS":
            return self._get_status()

        elif command == "EXECUTE_TASK":
            return self._execute_task(request.get("task", {}))

        elif command == "EXECUTE_SCRIPT":
            return self._execute_script(request.get("script", ""), request.get("args", []))

        elif command == "EXECUTE_CMD":
            return self._execute_cmd(request.get("cmd", ""))

        elif command == "GPU_STATUS":
            return self._get_gpu_status()

        elif command == "LM_STUDIO_STATUS":
            return self._get_lm_studio_status()

        elif command == "STOP":
            self.running = False
            return {"status": "ok", "message": "Worker arrete"}

        else:
            return {"status": "error", "message": f"Commande inconnue: {command}"}

    def _get_status(self):
        """Retourner le statut du worker"""
        return {
            "status": "ok",
            "worker_id": self.worker_id,
            "running": self.running,
            "current_task": self.current_task,
            "stats": self.stats,
            "system": {
                "hostname": socket.gethostname(),
                "platform": sys.platform,
                "python": sys.version
            },
            "timestamp": datetime.now().isoformat()
        }

    def _execute_task(self, task):
        """Executer une tache"""
        task_id = task.get("id", "unknown")
        task_type = task.get("type", "")

        self.current_task = task_id
        self.log(f"Execution tache: {task_id} ({task_type})")

        try:
            result = None

            if task_type == "python_script":
                result = self._execute_script(task.get("script"), task.get("args", []))

            elif task_type == "shell_command":
                result = self._execute_cmd(task.get("command"))

            elif task_type == "ai_inference":
                result = self._run_ai_inference(task.get("prompt"), task.get("model"))

            else:
                result = {"status": "error", "message": f"Type de tache inconnu: {task_type}"}

            if result.get("status") == "ok":
                self.stats["tasks_completed"] += 1
            else:
                self.stats["tasks_failed"] += 1

            return result

        except Exception as e:
            self.stats["tasks_failed"] += 1
            return {"status": "error", "message": str(e)}
        finally:
            self.current_task = None

    def _execute_script(self, script_path, args=[]):
        """Executer un script Python"""
        try:
            cmd = [sys.executable, script_path] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            return {
                "status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Timeout (5 min)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _execute_cmd(self, cmd):
        """Executer une commande shell"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

            return {
                "status": "ok" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Timeout (2 min)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_gpu_status(self):
        """Obtenir statut GPU via nvidia-smi"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )

            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 4:
                        gpus.append({
                            "name": parts[0],
                            "memory_used_mb": int(parts[1]),
                            "memory_total_mb": int(parts[2]),
                            "utilization": int(parts[3])
                        })

            return {"status": "ok", "gpus": gpus}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_lm_studio_status(self):
        """Verifier si LM Studio est actif"""
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:1234/v1/models")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return {
                    "status": "ok",
                    "lm_studio": "running",
                    "models": data.get("data", [])
                }
        except Exception as e:
            return {"status": "ok", "lm_studio": "offline", "error": str(e)}

    def _run_ai_inference(self, prompt, model=None):
        """Executer inference IA via LM Studio"""
        try:
            import urllib.request

            payload = {
                "model": model or "nvidia/nemotron-3-nano",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7
            }

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                "http://127.0.0.1:1234/v1/chat/completions",
                data=data,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return {
                    "status": "ok",
                    "response": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    "model": model,
                    "usage": result.get("usage", {})
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _heartbeat_loop(self):
        """Envoyer heartbeat periodique au Master"""
        master_ip = self.config.get("machines", {}).get("master", {}).get("ip", "192.168.1.85")
        master_port = self.config.get("machines", {}).get("master", {}).get("port", 5000)
        interval = self.config.get("communication", {}).get("heartbeat_interval", 5)

        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((master_ip, master_port))

                heartbeat = {
                    "command": "HEARTBEAT",
                    "worker_id": self.worker_id,
                    "status": "alive",
                    "current_task": self.current_task,
                    "timestamp": datetime.now().isoformat()
                }

                sock.send(json.dumps(heartbeat).encode('utf-8'))
                sock.close()

                self.stats["last_heartbeat"] = datetime.now().isoformat()

            except Exception as e:
                # Master peut ne pas etre disponible, pas grave
                pass

            time.sleep(interval)

    def stop(self):
        """Arreter le serveur"""
        self.running = False
        if self.socket:
            self.socket.close()
        self.log("Worker arrete")


def main():
    # Detecter le port selon la machine
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    if "26" in local_ip or local_ip == "192.168.1.26":
        port = 5001
    elif "113" in local_ip or local_ip == "192.168.1.113":
        port = 5002
    else:
        port = 5001  # Default

    print(f"Demarrage Worker sur port {port}")
    print(f"IP detectee: {local_ip}")

    worker = WorkerServer(port=port)

    try:
        worker.start()
    except KeyboardInterrupt:
        print("\nArret demande...")
        worker.stop()


if __name__ == "__main__":
    main()
