"""
CLUSTER MONITOR - Outil de surveillance du cluster
Peut etre execute depuis n'importe quelle machine
"""

import socket
import json
import sys
import time
from datetime import datetime

# Configuration du cluster
CLUSTER_CONFIG = {
    "master": {"ip": "192.168.1.85", "port": 5000, "name": "MASTER-WIN11"},
    "worker1": {"ip": "192.168.1.26", "port": 5001, "name": "WIN-TBOT (GPU)"},
    "worker2": {"ip": "192.168.1.113", "port": 5002, "name": "SERVER-3"}
}

def send_command(ip, port, command, timeout=10):
    """Envoyer une commande et recevoir la reponse"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        sock.send(json.dumps(command).encode('utf-8'))
        response = sock.recv(65536).decode('utf-8')
        sock.close()
        return json.loads(response) if response else None
    except socket.timeout:
        return {"error": "timeout"}
    except ConnectionRefusedError:
        return {"error": "connection_refused"}
    except Exception as e:
        return {"error": str(e)}

def check_connectivity():
    """Verifier la connectivite reseau basique (ping)"""
    import subprocess

    print("\n" + "=" * 60)
    print("   TEST CONNECTIVITE RESEAU")
    print("=" * 60)

    for node_id, config in CLUSTER_CONFIG.items():
        ip = config["ip"]
        name = config["name"]

        try:
            # Ping (Windows)
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", ip],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Extraire le temps
                import re
                match = re.search(r'temps[=<](\d+)', result.stdout, re.IGNORECASE)
                if not match:
                    match = re.search(r'time[=<](\d+)', result.stdout, re.IGNORECASE)
                latency = match.group(1) if match else "?"
                print(f"  [OK] {node_id:10} ({ip:15}) - {name:20} | Latence: {latency}ms")
            else:
                print(f"  [--] {node_id:10} ({ip:15}) - {name:20} | INJOIGNABLE")

        except Exception as e:
            print(f"  [!!] {node_id:10} ({ip:15}) - {name:20} | Erreur: {e}")

def check_services():
    """Verifier les services (Worker/Master) sur chaque machine"""
    print("\n" + "=" * 60)
    print("   STATUS SERVICES CLUSTER")
    print("=" * 60)

    for node_id, config in CLUSTER_CONFIG.items():
        ip = config["ip"]
        port = config["port"]
        name = config["name"]

        result = send_command(ip, port, {"command": "STATUS"})

        if result and "error" not in result:
            status = result.get("status", "unknown")
            worker_id = result.get("worker_id", node_id)
            current_task = result.get("current_task", "-")
            stats = result.get("stats", {})

            print(f"\n  [{node_id.upper()}] {name} ({ip}:{port})")
            print(f"    Status: ONLINE")
            print(f"    Worker ID: {worker_id}")
            print(f"    Tache en cours: {current_task or 'Aucune'}")
            print(f"    Taches completees: {stats.get('tasks_completed', 0)}")
            print(f"    Dernier heartbeat: {stats.get('last_heartbeat', '-')}")
        else:
            error = result.get("error", "unknown") if result else "no response"
            print(f"\n  [{node_id.upper()}] {name} ({ip}:{port})")
            print(f"    Status: OFFLINE ({error})")

def check_gpu_status():
    """Verifier le status GPU des workers"""
    print("\n" + "=" * 60)
    print("   STATUS GPU")
    print("=" * 60)

    for node_id, config in CLUSTER_CONFIG.items():
        if node_id == "master":
            continue

        ip = config["ip"]
        port = config["port"]
        name = config["name"]

        result = send_command(ip, port, {"command": "GPU_STATUS"})

        print(f"\n  [{node_id.upper()}] {name}")

        if result and result.get("status") == "ok":
            gpus = result.get("gpus", [])
            if gpus:
                for i, gpu in enumerate(gpus):
                    used = gpu.get("memory_used_mb", 0)
                    total = gpu.get("memory_total_mb", 0)
                    util = gpu.get("utilization", 0)
                    pct = (used / total * 100) if total > 0 else 0

                    bar_len = 20
                    filled = int(bar_len * pct / 100)
                    bar = "█" * filled + "░" * (bar_len - filled)

                    print(f"    GPU {i}: {gpu.get('name', 'Unknown')}")
                    print(f"    Memoire: [{bar}] {used}/{total} MB ({pct:.1f}%)")
                    print(f"    Utilisation: {util}%")
            else:
                print("    Pas de GPU detecte")
        else:
            error = result.get("error", result.get("message", "unknown")) if result else "offline"
            print(f"    Status: Non disponible ({error})")

def check_lm_studio():
    """Verifier LM Studio sur worker1"""
    print("\n" + "=" * 60)
    print("   STATUS LM STUDIO (Worker1 - 192.168.1.26)")
    print("=" * 60)

    config = CLUSTER_CONFIG.get("worker1")
    if not config:
        print("  Worker1 non configure")
        return

    result = send_command(config["ip"], config["port"], {"command": "LM_STUDIO_STATUS"})

    if result and result.get("status") == "ok":
        lm_status = result.get("lm_studio", "unknown")
        print(f"\n  LM Studio: {lm_status.upper()}")

        if lm_status == "running":
            models = result.get("models", [])
            print(f"  Modeles charges: {len(models)}")
            for model in models:
                model_id = model.get("id", "unknown")
                print(f"    - {model_id}")
    else:
        print(f"\n  LM Studio: NON DISPONIBLE")

def run_cluster_test():
    """Executer un test complet du cluster"""
    print("\n" + "=" * 60)
    print("   TEST EXECUTION CLUSTER")
    print("=" * 60)

    # Test sur worker1
    config = CLUSTER_CONFIG.get("worker1")
    if config:
        print(f"\n  Test Worker1 ({config['ip']})...")
        result = send_command(
            config["ip"],
            config["port"],
            {"command": "EXECUTE_CMD", "cmd": "echo OK && hostname"}
        )

        if result and result.get("status") == "ok":
            print(f"    Resultat: {result.get('stdout', '').strip()}")
        else:
            print(f"    Erreur: {result}")

    # Test sur worker2
    config = CLUSTER_CONFIG.get("worker2")
    if config:
        print(f"\n  Test Worker2 ({config['ip']})...")
        result = send_command(
            config["ip"],
            config["port"],
            {"command": "EXECUTE_CMD", "cmd": "echo OK && hostname"}
        )

        if result and result.get("status") == "ok":
            print(f"    Resultat: {result.get('stdout', '').strip()}")
        else:
            print(f"    Erreur: {result}")

def show_dashboard():
    """Afficher un dashboard complet"""
    print("\n")
    print("+" + "=" * 58 + "+")
    print("|" + "   TRADING AI CLUSTER - DASHBOARD".center(58) + "|")
    print("|" + f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(58) + "|")
    print("+" + "=" * 58 + "+")

    # Status rapide de chaque node
    print("| NODE        | IP              | PORT  | STATUS        |")
    print("+" + "-" * 58 + "+")

    for node_id, config in CLUSTER_CONFIG.items():
        ip = config["ip"]
        port = config["port"]

        result = send_command(ip, port, {"command": "PING"}, timeout=3)
        status = "ONLINE" if result and result.get("status") == "ok" else "OFFLINE"
        status_symbol = "[+]" if status == "ONLINE" else "[-]"

        line = f"| {node_id:10} | {ip:15} | {port:5} | {status_symbol} {status:8} |"
        print(line)

    print("+" + "=" * 58 + "+")

def main():
    """Point d'entree principal"""
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        if cmd == "ping":
            check_connectivity()
        elif cmd == "status":
            check_services()
        elif cmd == "gpu":
            check_gpu_status()
        elif cmd == "lm":
            check_lm_studio()
        elif cmd == "test":
            run_cluster_test()
        elif cmd == "all":
            check_connectivity()
            check_services()
            check_gpu_status()
            check_lm_studio()
        else:
            print(f"Commande inconnue: {cmd}")
            print("Usage: python cluster_monitor.py [ping|status|gpu|lm|test|all]")
    else:
        # Dashboard par defaut
        show_dashboard()
        print("\nCommandes: ping | status | gpu | lm | test | all")

if __name__ == "__main__":
    main()
