#!/usr/bin/env python3
"""
JARVIS Advanced CLI Interface
Commandes: cluster, trading, voice, agent, config, status
Mode interactif avec autocomplétion et historique
"""

import argparse
import json
import sys
import os
import readline
import time
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

try:
    import requests
    from requests.exceptions import RequestException, ConnectionError
except ImportError:
    print("ERROR: requests library required. pip install requests")
    sys.exit(1)

try:
    from tabulate import tabulate
except ImportError:
    print("ERROR: tabulate library required. pip install tabulate")
    sys.exit(1)


class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    DIM = '\033[2m'


class JARVISClient:
    """SDK Client for JARVIS Gateway"""
    
    def __init__(self, gateway_url: str = "http://127.0.0.1:8900", token: Optional[str] = None, verbose: bool = False):
        self.gateway_url = gateway_url.rstrip('/')
        self.token = token or self._get_jwt_token()
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.connected = self._test_connection()
        
    def _get_jwt_token(self) -> str:
        """Get JWT token from gateway"""
        try:
            resp = requests.post(f"{self.gateway_url}/auth/token", json={"auto": True}, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("token", "default_token")
        except:
            pass
        return "default_token"
    
    def _test_connection(self) -> bool:
        """Test gateway connection"""
        try:
            resp = self.session.get(f"{self.gateway_url}/health", timeout=3)
            return resp.status_code == 200
        except:
            return False
    
    def _log(self, msg: str):
        if self.verbose:
            print(f"{Colors.DIM}[DEBUG] {msg}{Colors.RESET}")
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request"""
        try:
            url = f"{self.gateway_url}{endpoint}"
            self._log(f"{method} {url}")
            resp = self.session.request(method, url, timeout=10, **kwargs)
            resp.raise_for_status()
            return resp.json() if resp.content else {"status": "ok"}
        except ConnectionError:
            return {"error": "Connection refused", "status": "offline"}
        except RequestException as e:
            return {"error": str(e), "status": "error"}
    
    # ===== CLUSTER COMMANDS =====
    
    def cluster_health(self) -> Dict:
        return self._request("GET", "/cluster/health")
    
    def cluster_query(self, query: str) -> Dict:
        return self._request("POST", "/cluster/query", json={"prompt": query})
    
    def cluster_consensus(self, prompt: str, timeout: int = 30) -> Dict:
        return self._request("POST", "/cluster/consensus", json={"prompt": prompt, "timeout": timeout})
    
    def cluster_gpu_stats(self) -> Dict:
        return self._request("GET", "/cluster/gpu/stats")
    
    def cluster_models(self) -> Dict:
        return self._request("GET", "/cluster/models")
    
    # ===== TRADING COMMANDS =====
    
    def trading_scan(self, coins: int = 50, top: int = 10) -> Dict:
        return self._request("POST", "/trading/scan", json={"coins": coins, "top": top})
    
    def trading_positions(self) -> Dict:
        return self._request("GET", "/trading/positions")
    
    def trading_signals(self, min_score: float = 0.7) -> Dict:
        return self._request("GET", "/trading/signals", params={"min_score": min_score})
    
    def trading_execute_signal(self, signal_id: int, dry_run: bool = True) -> Dict:
        return self._request("POST", f"/trading/signals/{signal_id}/execute", json={"dry_run": dry_run})
    
    def trading_close_position(self, symbol: str) -> Dict:
        return self._request("POST", f"/trading/positions/{symbol}/close")
    
    # ===== VOICE COMMANDS =====
    
    def voice_recognize(self, audio_path: str) -> Dict:
        return self._request("POST", "/voice/recognize", json={"audio_path": audio_path})
    
    def voice_tts(self, text: str) -> Dict:
        return self._request("POST", "/voice/tts", json={"text": text})
    
    def voice_analytics(self) -> Dict:
        return self._request("GET", "/voice/analytics")
    
    # ===== AGENT COMMANDS =====
    
    def agent_list(self) -> Dict:
        return self._request("GET", "/agents")
    
    def agent_start(self, agent_name: str) -> Dict:
        return self._request("POST", f"/agents/{agent_name}/start")
    
    def agent_stop(self, agent_name: str) -> Dict:
        return self._request("POST", f"/agents/{agent_name}/stop")
    
    def agent_status(self, agent_name: str) -> Dict:
        return self._request("GET", f"/agents/{agent_name}/status")
    
    # ===== CONFIG COMMANDS =====
    
    def config_get(self, key: str = None) -> Dict:
        endpoint = f"/config/{key}" if key else "/config"
        return self._request("GET", endpoint)
    
    def config_set(self, key: str, value: Any) -> Dict:
        return self._request("POST", "/config", json={"key": key, "value": value})
    
    def config_reset(self) -> Dict:
        return self._request("POST", "/config/reset")
    
    # ===== STATUS COMMANDS =====
    
    def status_dashboard(self) -> Dict:
        return self._request("GET", "/status/dashboard")


class JARVISCli:
    """Interactive CLI for JARVIS"""
    
    def __init__(self, verbose: bool = False, quiet: bool = False, json_output: bool = False):
        self.client = JARVISClient(verbose=verbose)
        self.verbose = verbose
        self.quiet = quiet
        self.json_output = json_output
        self.history_file = Path.home() / ".jarvis_history"
        self._load_history()
        self.commands = {
            "cluster": self._cmd_cluster,
            "trading": self._cmd_trading,
            "voice": self._cmd_voice,
            "agent": self._cmd_agent,
            "config": self._cmd_config,
            "status": self._cmd_status,
            "exit": self._cmd_exit,
            "help": self._cmd_help,
        }
    
    def _load_history(self):
        """Load command history from file"""
        if self.history_file.exists():
            readline.read_history_file(str(self.history_file))
        readline.set_history_length(500)
    
    def _save_history(self):
        """Save command history"""
        try:
            readline.write_history_file(str(self.history_file))
        except:
            pass
    
    def _print_status(self, status: str, level: str = "info"):
        """Print colored status message"""
        if self.quiet:
            return
        
        colors = {
            "ok": Colors.GREEN,
            "warning": Colors.YELLOW,
            "error": Colors.RED,
            "info": Colors.BLUE,
        }
        color = colors.get(level, Colors.WHITE)
        symbol = {"ok": "✓", "warning": "⚠", "error": "✗", "info": "ℹ"}.get(level, "•")
        print(f"{color}{symbol} {status}{Colors.RESET}")
    
    def _format_output(self, data: Dict, title: str = None):
        """Format output as JSON or table"""
        if self.json_output or not self.quiet:
            if title and not self.json_output:
                print(f"\n{Colors.BOLD}{Colors.CYAN}{title}{Colors.RESET}")
            
            if self.json_output:
                print(json.dumps(data, indent=2))
            else:
                # Format as table if possible
                if isinstance(data, dict):
                    if "nodes" in data:
                        headers = ["Node", "Status", "CPU", "GPU", "Memory"]
                        rows = []
                        for node, info in data.get("nodes", {}).items():
                            status = Colors.GREEN + "online" + Colors.RESET if info.get("online") else Colors.RED + "offline" + Colors.RESET
                            rows.append([node, status, info.get("cpu", "N/A"), info.get("gpu", "N/A"), info.get("memory", "N/A")])
                        print(tabulate(rows, headers=headers, tablefmt="grid"))
                    elif "data" in data or "results" in data:
                        items = data.get("data") or data.get("results", [])
                        if isinstance(items, list) and items and isinstance(items[0], dict):
                            headers = list(items[0].keys())
                            rows = [[item.get(k, "N/A") for k in headers] for item in items]
                            print(tabulate(rows, headers=headers, tablefmt="grid"))
                    else:
                        for k, v in data.items():
                            if not isinstance(v, (dict, list)):
                                print(f"  {Colors.BOLD}{k}{Colors.RESET}: {v}")
    
    def _cmd_cluster(self, args: list):
        """Cluster subcommands"""
        if not args:
            print(f"Usage: cluster [health|query|consensus|gpu|models]")
            return
        
        subcmd = args[0]
        
        if subcmd == "health":
            result = self.client.cluster_health()
            self._format_output(result, "Cluster Health")
            if result.get("status") == "ok":
                self._print_status(f"Cluster: {result.get('nodes_online', 0)} nodes online", "ok")
        
        elif subcmd == "query" and len(args) > 1:
            query = " ".join(args[1:])
            result = self.client.cluster_query(query)
            self._format_output(result, "Cluster Query Result")
        
        elif subcmd == "consensus" and len(args) > 1:
            prompt = " ".join(args[1:])
            self._print_status("Running consensus across cluster...", "info")
            result = self.client.cluster_consensus(prompt)
            self._format_output(result, "Consensus Result")
        
        elif subcmd == "gpu":
            result = self.client.cluster_gpu_stats()
            self._format_output(result, "GPU Statistics")
        
        elif subcmd == "models":
            result = self.client.cluster_models()
            self._format_output(result, "Loaded Models")
        
        else:
            print(f"Unknown subcommand: {subcmd}")
    
    def _cmd_trading(self, args: list):
        """Trading subcommands"""
        if not args:
            print(f"Usage: trading [scan|positions|signals|execute|close]")
            return
        
        subcmd = args[0]
        
        if subcmd == "scan":
            coins = int(args[1]) if len(args) > 1 else 50
            self._print_status(f"Scanning {coins} coins...", "info")
            result = self.client.trading_scan(coins=coins)
            self._format_output(result, "Trading Scan Results")
        
        elif subcmd == "positions":
            result = self.client.trading_positions()
            self._format_output(result, "Open Positions")
        
        elif subcmd == "signals":
            min_score = float(args[1]) if len(args) > 1 else 0.7
            result = self.client.trading_signals(min_score=min_score)
            self._format_output(result, "Trading Signals")
        
        elif subcmd == "execute" and len(args) > 1:
            signal_id = int(args[1])
            dry_run = "dry_run" in args or True
            result = self.client.trading_execute_signal(signal_id, dry_run=dry_run)
            self._format_output(result, "Signal Execution")
        
        elif subcmd == "close" and len(args) > 1:
            symbol = args[1]
            result = self.client.trading_close_position(symbol)
            self._print_status(f"Closed position: {symbol}", "ok")
        
        else:
            print(f"Unknown subcommand: {subcmd}")
    
    def _cmd_voice(self, args: list):
        """Voice subcommands"""
        if not args:
            print(f"Usage: voice [recognize|tts|analytics]")
            return
        
        subcmd = args[0]
        
        if subcmd == "recognize" and len(args) > 1:
            audio_path = args[1]
            result = self.client.voice_recognize(audio_path)
            self._format_output(result, "Voice Recognition Result")
        
        elif subcmd == "tts" and len(args) > 1:
            text = " ".join(args[1:])
            result = self.client.voice_tts(text)
            self._print_status("TTS audio generated", "ok")
        
        elif subcmd == "analytics":
            result = self.client.voice_analytics()
            self._format_output(result, "Voice Pipeline Analytics")
        
        else:
            print(f"Unknown subcommand: {subcmd}")
    
    def _cmd_agent(self, args: list):
        """Agent subcommands"""
        if not args:
            print(f"Usage: agent [list|start|stop|status]")
            return
        
        subcmd = args[0]
        
        if subcmd == "list":
            result = self.client.agent_list()
            self._format_output(result, "Active Agents")
        
        elif subcmd == "start" and len(args) > 1:
            agent = args[1]
            result = self.client.agent_start(agent)
            self._print_status(f"Started agent: {agent}", "ok")
        
        elif subcmd == "stop" and len(args) > 1:
            agent = args[1]
            result = self.client.agent_stop(agent)
            self._print_status(f"Stopped agent: {agent}", "ok")
        
        elif subcmd == "status" and len(args) > 1:
            agent = args[1]
            result = self.client.agent_status(agent)
            self._format_output(result, f"Agent Status: {agent}")
        
        else:
            print(f"Unknown subcommand: {subcmd}")
    
    def _cmd_config(self, args: list):
        """Config subcommands"""
        if not args:
            print(f"Usage: config [get|set|reset]")
            return
        
        subcmd = args[0]
        
        if subcmd == "get":
            key = args[1] if len(args) > 1 else None
            result = self.client.config_get(key)
            self._format_output(result, "Configuration")
        
        elif subcmd == "set" and len(args) > 2:
            key, value = args[1], args[2]
            result = self.client.config_set(key, value)
            self._print_status(f"Set {key} = {value}", "ok")
        
        elif subcmd == "reset":
            result = self.client.config_reset()
            self._print_status("Configuration reset", "ok")
        
        else:
            print(f"Unknown subcommand: {subcmd}")
    
    def _cmd_status(self, args: list):
        """Show dashboard"""
        result = self.client.status_dashboard()
        self._format_output(result, "JARVIS Status Dashboard")
    
    def _cmd_help(self, args: list):
        """Show help"""
        print(f"""
{Colors.BOLD}JARVIS CLI Commands:{Colors.RESET}

{Colors.CYAN}cluster{Colors.RESET}
  health              - Check cluster health
  query <prompt>      - Query cluster nodes
  consensus <prompt>  - Consensus across all nodes
  gpu                 - GPU statistics
  models              - List loaded models

{Colors.CYAN}trading{Colors.RESET}
  scan [coins]        - Scan coins for signals
  positions           - Show open positions
  signals [score]     - List trading signals
  execute <id>        - Execute signal
  close <symbol>      - Close position

{Colors.CYAN}voice{Colors.RESET}
  recognize <audio>   - Recognize audio
  tts <text>          - Text to speech
  analytics           - Voice analytics

{Colors.CYAN}agent{Colors.RESET}
  list                - List active agents
  start <name>        - Start agent
  stop <name>         - Stop agent
  status <name>       - Agent status

{Colors.CYAN}config{Colors.RESET}
  get [key]           - Get config
  set <key> <value>   - Set config
  reset               - Reset to defaults

{Colors.CYAN}status{Colors.RESET}
  - Show full dashboard

{Colors.CYAN}Global flags:{Colors.RESET}
  -v, --verbose       - Verbose output
  -q, --quiet         - Quiet mode
  --json              - JSON output
        """)
    
    def _cmd_exit(self, args: list):
        """Exit CLI"""
        self._save_history()
        print("Goodbye!")
        sys.exit(0)
    
    def run_command(self, command: str):
        """Run a command"""
        parts = command.strip().split()
        if not parts or parts[0] == "":
            return
        
        cmd = parts[0]
        args = parts[1:]
        
        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            self._print_status(f"Unknown command: {cmd}", "error")
    
    def repl(self):
        """Interactive REPL"""
        if not self.client.connected:
            self._print_status("Warning: Gateway not responding", "warning")
        
        print(f"{Colors.BOLD}{Colors.CYAN}JARVIS CLI v1.0{Colors.RESET}")
        print(f"Type 'help' for commands, 'exit' to quit\n")
        
        while True:
            try:
                cmd = input(f"{Colors.BOLD}JARVIS>{Colors.RESET} ").strip()
                if cmd:
                    self.run_command(cmd)
            except KeyboardInterrupt:
                print()
                self._cmd_exit([])
            except EOFError:
                self._cmd_exit([])


def main():
    parser = argparse.ArgumentParser(description="JARVIS Advanced CLI", prog="jarvis")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--gateway", default="http://127.0.0.1:8900", help="Gateway URL")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Cluster subcommands
    cluster_parser = subparsers.add_parser("cluster", help="Cluster commands")
    cluster_parser.add_argument("subcommand", help="health|query|consensus|gpu|models")
    cluster_parser.add_argument("args", nargs="*", help="Arguments")
    
    # Trading subcommands
    trading_parser = subparsers.add_parser("trading", help="Trading commands")
    trading_parser.add_argument("subcommand", help="scan|positions|signals|execute|close")
    trading_parser.add_argument("args", nargs="*", help="Arguments")
    
    # Voice subcommands
    voice_parser = subparsers.add_parser("voice", help="Voice commands")
    voice_parser.add_argument("subcommand", help="recognize|tts|analytics")
    voice_parser.add_argument("args", nargs="*", help="Arguments")
    
    # Agent subcommands
    agent_parser = subparsers.add_parser("agent", help="Agent commands")
    agent_parser.add_argument("subcommand", help="list|start|stop|status")
    agent_parser.add_argument("args", nargs="*", help="Arguments")
    
    # Config subcommands
    config_parser = subparsers.add_parser("config", help="Config commands")
    config_parser.add_argument("subcommand", help="get|set|reset")
    config_parser.add_argument("args", nargs="*", help="Arguments")
    
    # Status
    subparsers.add_parser("status", help="Show dashboard")
    
    args = parser.parse_args()
    
    cli = JARVISCli(verbose=args.verbose, quiet=args.quiet, json_output=args.json)
    
    if args.command:
        # Execute single command
        if args.command == "cluster":
            cli._cmd_cluster([args.subcommand] + args.args)
        elif args.command == "trading":
            cli._cmd_trading([args.subcommand] + args.args)
        elif args.command == "voice":
            cli._cmd_voice([args.subcommand] + args.args)
        elif args.command == "agent":
            cli._cmd_agent([args.subcommand] + args.args)
        elif args.command == "config":
            cli._cmd_config([args.subcommand] + args.args)
        elif args.command == "status":
            cli._cmd_status([])
    else:
        # Interactive mode
        cli.repl()


if __name__ == "__main__":
    main()
