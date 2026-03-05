"""
MASTER SERVER - Gestionnaire de Serveur Distribue
Machine: Master (192.168.1.85) - Windows 11 Pro
Role: Distribuer les taches aux Workers
"""

import socket
import json
import threading
import time
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
BASE_DIR = Path("C:/CLAUDE_WORKSPACE/SERVER_MANAGER")
CONFIG_FILE = BASE_DIR / "config" / "network_config.json"
LOG_DIR = BASE_DIR / "logs"
TASK_DIR = BASE_DIR / "tasks"

class MasterServer:
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
        self.failed_tasks = []

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
            self.log(f"ERREUR config: {e}")
            return self._default_config()

    def _default_config(self):
        """Configuration par defaut"""
        return {
            "machines": {
                "worker1": {"ip": "192.168.1.26", "port": 5001},
                "worker2": {"ip": "192.168.1.113", "port": 5002}
            },
            "communication": {
                "heartbeat_interval": 5,
                "timeout": 30
            }
        }

    def log(self, message, level="INFO"):
        """Logger un message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] [MASTER] {message}"
        print(log_line)

        # Sauvegarder dans fichier
        log_file = LOG_DIR / f"master_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + "\n")
        except:
            pass

    def start(self):
        """Demarrer le serveur Master"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            self.running = True
            self.stats["uptime_start"] = datetime.now().isoformat()

            self.log("=" * 50)
            self.log("    MASTER SERVER - TRADING AI CLUSTER")
            self.log("=" * 50)
            self.log(f"Ecoute sur {self.host}:{self.port}")

            # Demarrer threads de fond
            threading.Thread(target=self._worker_monitor, daemon=True).start()
            threading.Thread(target=self._task_dispatcher, daemon=True).start()
            threading.Thread(target=self._heartbeat_listener, daemon=True).start()

            # Scan initial des workers
            self._scan_workers()

            # Boucle principale - interface console
            self._console_loop()

        except Exception as e:
            self.log(f"Erreur demarrage: {e}", "ERROR")
        finally:
            self.stop()

    def _heartbeat_listener(self):
        """Ecouter les heartbeats des workers"""
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                data = client_socket.recv(4096).decode('utf-8')

                if data:
                    request = json.loads(data)

                    if request.get("command") == "HEARTBEAT":
                        worker_id = request.get("worker_id")
                        if worker_id:
                            self.workers[worker_id] = {
                                "ip": address[0],
                                "last_seen": datetime.now().isoformat(),
                                "status": request.get("status", "unknown"),
                                "current_task": request.get("current_task")
                            }

                client_socket.close()

            except Exception as e:
                if self.running:
                    pass  # Ignorer erreurs mineures

    def _scan_workers(self):
        """Scanner tous les workers configures"""
        self.log("Scan des workers...")

        machines = self.config.get("machines", {})
        for worker_id, info in machines.items():
            if info.get("role") == "worker" or worker_id.startswith("worker"):
                ip = info.get("ip")
                port = info.get("port", 5001)

                result = self.send_command(ip, port, {"command": "PING"})

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
        """Surveiller l'etat des workers"""
        while self.running:
            time.sleep(30)  # Check toutes les 30s
            self._scan_workers()

    def _task_dispatcher(self):
        """Distribuer les taches aux workers"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)

                # Trouver un worker disponible
                worker = self._select_worker(task)

                if worker:
                    self.log(f"Distribution tache {task.get('id')} vers {worker['id']}")
                    result = self._send_task(worker, task)

                    if result.get("status") == "ok":
                        self.stats["tasks_completed"] += 1
                        self.completed_tasks.append({
                            "task": task,
                            "result": result,
                            "worker": worker['id'],
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        self.stats["tasks_failed"] += 1
                        self.failed_tasks.append({
                            "task": task,
                            "error": result,
                            "worker": worker['id'],
                            "timestamp": datetime.now().isoformat()
                        })
                else:
                    # Remettre en queue si pas de worker
                    self.task_queue.put(task)
                    time.sleep(5)

            except queue.Empty:
                continue
            except Exception as e:
                self.log(f"Erreur dispatcher: {e}", "ERROR")

    def _select_worker(self, task) -> Optional[dict]:
        """Selectionner le meilleur worker pour une tache"""
        task_type = task.get("type", "")

        # Priorite GPU pour inference IA
        if task_type == "ai_inference":
            if "worker1" in self.workers and self.workers["worker1"].get("status") == "online":
                return {"id": "worker1", **self.workers["worker1"]}

        # Round-robin pour autres taches
        for worker_id, info in self.workers.items():
            if info.get("status") == "online" and not info.get("current_task"):
                return {"id": worker_id, **info}

        # Fallback: premier worker online
        for worker_id, info in self.workers.items():
            if info.get("status") == "online":
                return {"id": worker_id, **info}

        return None

    def _send_task(self, worker: dict, task: dict) -> dict:
        """Envoyer une tache a un worker"""
        return self.send_command(
            worker.get("ip"),
            worker.get("port"),
            {"command": "EXECUTE_TASK", "task": task}
        )

    def send_command(self, ip: str, port: int, command: dict, timeout: int = 30) -> dict:
        """Envoyer une commande a un worker"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, port))

            sock.send(json.dumps(command).encode('utf-8'))

            response = sock.recv(65536).decode('utf-8')
            sock.close()

            return json.loads(response) if response else {"status": "error", "message": "No response"}

        except socket.timeout:
            return {"status": "error", "message": "Timeout"}
        except ConnectionRefusedError:
            return {"status": "error", "message": "Connection refused"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def add_task(self, task: dict):
        """Ajouter une tache a la file"""
        task["id"] = task.get("id", f"task_{int(time.time()*1000)}")
        task["created"] = datetime.now().isoformat()

        self.task_queue.put(task)
        self.stats["tasks_distributed"] += 1
        self.log(f"Tache ajoutee: {task['id']}")

    def _console_loop(self):
        """Boucle console interactive"""
        print("\n" + "=" * 50)
        print("COMMANDES DISPONIBLES:")
        print("  status    - Voir etat du cluster")
        print("  workers   - Liste des workers")
        print("  scan      - Re-scanner les workers")
        print("  ping <w>  - Ping un worker (worker1/worker2)")
        print("  gpu       - Statut GPU des workers")
        print("  task <t>  - Ajouter tache (test)")
        print("  ai <msg>  - Inference IA")
        print("  cmd <c>   - Executer commande sur workers")
        print("  quit      - Arreter le serveur")
        print("=" * 50 + "\n")

        while self.running:
            try:
                cmd = input("MASTER> ").strip()
                if not cmd:
                    continue

                parts = cmd.split(maxsplit=1)
                action = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if action == "quit" or action == "exit":
                    self.running = False

                elif action == "status":
                    self._show_status()

                elif action == "workers":
                    self._show_workers()

                elif action == "scan":
                    self._scan_workers()

                elif action == "ping":
                    self._ping_worker(args or "worker1")

                elif action == "gpu":
                    self._show_gpu_status()

                elif action == "task":
                    self.add_task({"type": "shell_command", "command": args or "echo test"})

                elif action == "ai":
                    if args:
                        self.add_task({"type": "ai_inference", "prompt": args})
                    else:
                        print("Usage: ai <prompt>")

                elif action == "cmd":
                    if args:
                        self._broadcast_command(args)
                    else:
                        print("Usage: cmd <commande>")

                else:
                    print(f"Commande inconnue: {action}")

            except KeyboardInterrupt:
                print("\nArret demande...")
                self.running = False
            except EOFError:
                break

    def _show_status(self):
        """Afficher statut du cluster"""
        print("\n" + "=" * 40)
        print("      STATUT CLUSTER")
        print("=" * 40)
        print(f"Uptime: {self.stats['uptime_start']}")
        print(f"Workers online: {sum(1 for w in self.workers.values() if w.get('status') == 'online')}/{len(self.workers)}")
        print(f"Taches en queue: {self.task_queue.qsize()}")
        print(f"Taches completees: {self.stats['tasks_completed']}")
        print(f"Taches echouees: {self.stats['tasks_failed']}")
        print("=" * 40 + "\n")

    def _show_workers(self):
        """Afficher liste des workers"""
        print("\n" + "-" * 50)
        print("WORKERS:")
        for worker_id, info in self.workers.items():
            status = "ONLINE" if info.get("status") == "online" else "OFFLINE"
            task = info.get("current_task", "-")
            print(f"  {worker_id}: {info.get('ip')}:{info.get('port')} [{status}] Task: {task}")
        print("-" * 50 + "\n")

    def _ping_worker(self, worker_id):
        """Ping un worker specifique"""
        if worker_id not in self.workers:
            print(f"Worker inconnu: {worker_id}")
            return

        info = self.workers[worker_id]
        result = self.send_command(info['ip'], info['port'], {"command": "PING"})
        print(f"Ping {worker_id}: {result}")

    def _show_gpu_status(self):
        """Afficher statut GPU de tous les workers"""
        print("\nSTATUT GPU:")
        for worker_id, info in self.workers.items():
            if info.get("status") == "online":
                result = self.send_command(info['ip'], info['port'], {"command": "GPU_STATUS"})
                print(f"\n{worker_id} ({info['ip']}):")
                if result.get("status") == "ok":
                    for gpu in result.get("gpus", []):
                        print(f"  - {gpu['name']}: {gpu['memory_used_mb']}/{gpu['memory_total_mb']} MB ({gpu['utilization']}%)")
                else:
                    print(f"  Erreur: {result.get('message')}")

    def _broadcast_command(self, cmd):
        """Executer commande sur tous les workers"""
        print(f"\nExecution: {cmd}")
        for worker_id, info in self.workers.items():
            if info.get("status") == "online":
                result = self.send_command(info['ip'], info['port'], {"command": "EXECUTE_CMD", "cmd": cmd})
                print(f"\n[{worker_id}]:")
                if result.get("status") == "ok":
                    print(result.get("stdout", ""))
                else:
                    print(f"Erreur: {result.get('message')}")

    def stop(self):
        """Arreter le serveur"""
        self.running = False
        if self.socket:
            self.socket.close()
        self.log("Master arrete")


def main():
    print("=" * 50)
    print("  MASTER SERVER - TRADING AI CLUSTER")
    print("  Machine: 192.168.1.85 (Windows 11 Pro)")
    print("=" * 50)

    master = MasterServer(port=5000)

    try:
        master.start()
    except KeyboardInterrupt:
        print("\nArret...")
        master.stop()


if __name__ == "__main__":
    main()
