"""
MASTER DAEMON - Version non-interactive pour service Windows
Machine: Master (192.168.1.85) - Windows 11 Pro
Role: Distribuer les taches aux Workers (mode service)
"""

import socket
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import queue
import sys

# Configuration
BASE_DIR = Path("C:/CLAUDE_WORKSPACE/SERVER_MANAGER")
CONFIG_FILE = BASE_DIR / "config" / "network_config.json"
LOG_DIR = BASE_DIR / "logs"

class MasterDaemon:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False

        # Workers connectes
        self.workers: Dict[str, dict] = {}

        # File de taches
        self.task_queue = queue.Queue()
        self.completed_tasks = []

        # Charger config
        self.config = self._load_config()

        # Stats
        self.stats = {
            "tasks_distributed": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "uptime_start": None
        }

    def _load_config(self):
        """Charger la configuration reseau"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.log(f"Config par defaut utilise: {e}")
            return {
                "machines": {
                    "worker1": {"ip": "192.168.1.26", "port": 5001},
                    "worker2": {"ip": "192.168.1.113", "port": 5002}
                },
                "communication": {"heartbeat_interval": 5, "timeout": 30}
            }

    def log(self, message, level="INFO"):
        """Logger un message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] [MASTER-DAEMON] {message}"
        print(log_line, flush=True)

        # Sauvegarder dans fichier
        log_file = LOG_DIR / f"master_daemon_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + "\n")
        except:
            pass

    def start(self):
        """Demarrer le daemon Master"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            self.running = True
            self.stats["uptime_start"] = datetime.now().isoformat()

            self.log("=" * 50)
            self.log("    MASTER DAEMON - TRADING AI CLUSTER")
            self.log("=" * 50)
            self.log(f"Ecoute sur {self.host}:{self.port}")

            # Demarrer threads de fond
            threading.Thread(target=self._worker_monitor, daemon=True).start()
            threading.Thread(target=self._task_dispatcher, daemon=True).start()
            threading.Thread(target=self._status_reporter, daemon=True).start()

            # Scan initial des workers
            self._scan_workers()

            # Boucle principale - accepter connexions
            self._main_loop()

        except Exception as e:
            self.log(f"Erreur demarrage: {e}", "ERROR")
        finally:
            self.stop()

    def _main_loop(self):
        """Boucle principale - accepter et traiter les connexions"""
        self.log("Mode daemon actif - en attente de connexions...")

        while self.running:
            try:
                self.socket.settimeout(1.0)  # Permet de verifier self.running
                try:
                    client_socket, address = self.socket.accept()
                except socket.timeout:
                    continue

                # Thread pour traiter la connexion
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                ).start()

            except Exception as e:
                if self.running:
                    self.log(f"Erreur accept: {e}", "ERROR")

    def _handle_client(self, client_socket, address):
        """Traiter une connexion entrante"""
        try:
            data = client_socket.recv(65536).decode('utf-8')
            if not data:
                return

            request = json.loads(data)
            command = request.get("command", "")

            # Traiter la commande
            response = self._process_command(request, address)

            # Envoyer reponse
            client_socket.send(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.log(f"Erreur client {address}: {e}", "ERROR")
            try:
                client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()

    def _process_command(self, request, address):
        """Traiter une commande entrante"""
        command = request.get("command", "")

        if command == "PING":
            return {
                "status": "ok",
                "response": "PONG",
                "node": "master",
                "timestamp": datetime.now().isoformat()
            }

        elif command == "STATUS":
            return {
                "status": "ok",
                "node": "master",
                "running": self.running,
                "workers": {k: {"ip": v.get("ip"), "status": v.get("status")} for k, v in self.workers.items()},
                "stats": self.stats,
                "timestamp": datetime.now().isoformat()
            }

        elif command == "HEARTBEAT":
            worker_id = request.get("worker_id")
            if worker_id:
                self.workers[worker_id] = {
                    "ip": address[0],
                    "last_seen": datetime.now().isoformat(),
                    "status": request.get("status", "online"),
                    "current_task": request.get("current_task")
                }
            return {"status": "ok"}

        elif command == "ADD_TASK":
            task = request.get("task", {})
            self.add_task(task)
            return {"status": "ok", "task_id": task.get("id")}

        elif command == "GET_WORKERS":
            return {"status": "ok", "workers": self.workers}

        elif command == "SCAN_WORKERS":
            self._scan_workers()
            return {"status": "ok", "workers": self.workers}

        elif command == "STOP":
            self.running = False
            return {"status": "ok", "message": "Master daemon arrete"}

        else:
            return {"status": "error", "message": f"Commande inconnue: {command}"}

    def _scan_workers(self):
        """Scanner tous les workers configures"""
        self.log("Scan des workers...")

        machines = self.config.get("machines", {})
        for worker_id, info in machines.items():
            if info.get("role") == "worker" or worker_id.startswith("worker"):
                ip = info.get("ip")
                port = info.get("port", 5001)

                result = self._send_command(ip, port, {"command": "PING"})

                if result and result.get("status") == "ok":
                    self.workers[worker_id] = {
                        "ip": ip,
                        "port": port,
                        "last_seen": datetime.now().isoformat(),
                        "status": "online"
                    }
                    self.log(f"  [OK] {worker_id} ({ip}:{port}) - CONNECTE")
                else:
                    self.workers[worker_id] = {
                        "ip": ip,
                        "port": port,
                        "status": "offline"
                    }
                    self.log(f"  [--] {worker_id} ({ip}:{port}) - HORS LIGNE")

    def _worker_monitor(self):
        """Surveiller l'etat des workers periodiquement"""
        while self.running:
            time.sleep(30)
            self._scan_workers()

    def _task_dispatcher(self):
        """Distribuer les taches aux workers"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                worker = self._select_worker(task)

                if worker:
                    self.log(f"Distribution tache {task.get('id')} vers {worker['id']}")
                    result = self._send_command(
                        worker["ip"], worker["port"],
                        {"command": "EXECUTE_TASK", "task": task}
                    )

                    if result and result.get("status") == "ok":
                        self.stats["tasks_completed"] += 1
                    else:
                        self.stats["tasks_failed"] += 1
                else:
                    # Remettre en queue si pas de worker
                    self.task_queue.put(task)
                    time.sleep(5)

            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"Erreur dispatcher: {e}", "ERROR")

    def _status_reporter(self):
        """Rapport de status periodique"""
        while self.running:
            time.sleep(60)  # Toutes les minutes
            online = sum(1 for w in self.workers.values() if w.get("status") == "online")
            self.log(f"Status: {online}/{len(self.workers)} workers online, {self.task_queue.qsize()} taches en queue")

    def _select_worker(self, task) -> Optional[dict]:
        """Selectionner le meilleur worker pour une tache"""
        task_type = task.get("type", "")

        # Priorite GPU pour inference IA
        if task_type == "ai_inference":
            if "worker1" in self.workers and self.workers["worker1"].get("status") == "online":
                return {"id": "worker1", **self.workers["worker1"]}

        # Round-robin pour autres taches
        for worker_id, info in self.workers.items():
            if info.get("status") == "online":
                return {"id": worker_id, **info}

        return None

    def _send_command(self, ip: str, port: int, command: dict, timeout: int = 10) -> dict:
        """Envoyer une commande a un worker"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))
            sock.send(json.dumps(command).encode('utf-8'))
            response = sock.recv(65536).decode('utf-8')
            sock.close()
            return json.loads(response) if response else {"status": "error"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def add_task(self, task: dict):
        """Ajouter une tache a la file"""
        task["id"] = task.get("id", f"task_{int(time.time()*1000)}")
        task["created"] = datetime.now().isoformat()
        self.task_queue.put(task)
        self.stats["tasks_distributed"] += 1
        self.log(f"Tache ajoutee: {task['id']}")

    def stop(self):
        """Arreter le daemon"""
        self.running = False
        if self.socket:
            self.socket.close()
        self.log("Master daemon arrete")


def main():
    print("=" * 50)
    print("  MASTER DAEMON - TRADING AI CLUSTER")
    print("  Machine: 192.168.1.85 (Windows 11 Pro)")
    print("  Mode: Service/Daemon (non-interactif)")
    print("=" * 50)

    daemon = MasterDaemon(port=5000)

    try:
        daemon.start()
    except KeyboardInterrupt:
        print("\nArret demande...")
        daemon.stop()


if __name__ == "__main__":
    main()
