#!/usr/bin/env python3
"""
JARVIS CLI Dashboard
Real-time terminal dashboard with htop-like interface
Displays: Cluster Nodes | GPU Stats | Trading | Active Agents
"""

import curses
import json
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import deque
import requests
from pathlib import Path


class Colors:
    """Color codes for curses"""
    OK = 2
    WARNING = 3
    CRITICAL = 1
    INFO = 4
    HEADER = 5
    DIM = 6


class Dashboard:
    """JARVIS Real-time Dashboard"""
    
    def __init__(self, gateway: str = "http://127.0.0.1:8900", ws_url: str = "ws://127.0.0.1:9742"):
        self.gateway = gateway.rstrip('/')
        self.ws_url = ws_url
        self.token = self._get_token()
        self.running = True
        self.last_update = datetime.now()
        self.update_interval = 2  # seconds
        
        # Data caches
        self.cluster_health = {}
        self.gpu_stats = {}
        self.trading_data = {}
        self.agents = {}
        
        # History for sparklines (last 60 values)
        self.latency_history = deque(maxlen=60)
        self.gpu_temp_history = deque(maxlen=60)
        self.cpu_history = deque(maxlen=60)
        
        # Connection status
        self.ws_connected = False
        self.http_fallback = True
        self.start_time = datetime.now()
        
        self._setup_colors()
    
    def _get_token(self) -> str:
        """Get JWT token"""
        try:
            resp = requests.post(f"{self.gateway}/auth/token", json={"auto": True}, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("token", "default")
        except:
            pass
        return "default"
    
    def _setup_colors(self):
        """Initialize color pairs"""
        curses.init_pair(Colors.OK, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(Colors.WARNING, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(Colors.CRITICAL, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(Colors.INFO, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(Colors.HEADER, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(Colors.DIM, curses.COLOR_BLACK, curses.COLOR_BLACK)
    
    def _fetch_cluster_health(self) -> Dict:
        """Fetch cluster health from gateway"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = requests.get(f"{self.gateway}/cluster/health", headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {"status": "offline", "nodes": {}}
    
    def _fetch_gpu_stats(self) -> Dict:
        """Fetch GPU statistics"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = requests.get(f"{self.gateway}/cluster/gpu/stats", headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {"gpus": []}
    
    def _fetch_trading(self) -> Dict:
        """Fetch trading status"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = requests.get(f"{self.gateway}/trading/positions", headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {"positions": []}
    
    def _fetch_agents(self) -> Dict:
        """Fetch active agents"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            resp = requests.get(f"{self.gateway}/agents", headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass
        return {"agents": []}
    
    def _update_data(self):
        """Update all data from gateway"""
        while self.running:
            try:
                self.cluster_health = self._fetch_cluster_health()
                self.gpu_stats = self._fetch_gpu_stats()
                self.trading_data = self._fetch_trading()
                self.agents = self._fetch_agents()
                
                # Record metrics for history
                if self.cluster_health.get("nodes"):
                    for node, info in self.cluster_health["nodes"].items():
                        latency = info.get("latency_ms", 0)
                        self.latency_history.append(latency)
                
                if self.gpu_stats.get("gpus"):
                    for gpu in self.gpu_stats["gpus"]:
                        temp = gpu.get("temperature", 0)
                        self.gpu_temp_history.append(temp)
                
                self.last_update = datetime.now()
            except Exception as e:
                pass
            
            time.sleep(self.update_interval)
    
    def _sparkline(self, values: List[float], width: int = 20) -> str:
        """Generate ASCII sparkline"""
        if not values:
            return "─" * width
        
        sparkchars = "▁▂▃▄▅▆▇█"
        min_val = min(values) if values else 0
        max_val = max(values) if values else 1
        range_val = max_val - min_val if max_val > min_val else 1
        
        line = ""
        for val in list(values)[-width:]:
            normalized = (val - min_val) / range_val if range_val > 0 else 0
            idx = int(normalized * (len(sparkchars) - 1))
            line += sparkchars[max(0, min(idx, len(sparkchars) - 1))]
        
        return line.ljust(width, "─")
    
    def _get_status_color(self, status: str) -> int:
        """Get color for status"""
        if status == "online":
            return Colors.OK
        elif status == "warning":
            return Colors.WARNING
        else:
            return Colors.CRITICAL
    
    def _draw_header(self, stdscr, y: int, title: str) -> int:
        """Draw section header"""
        height, width = stdscr.getmaxyx()
        title_str = f" {title} ".center(width - 2)
        stdscr.attron(curses.color_pair(Colors.HEADER) | curses.A_BOLD)
        stdscr.addstr(y, 0, "█" + title_str + "█")
        stdscr.attroff(curses.color_pair(Colors.HEADER) | curses.A_BOLD)
        return y + 1
    
    def _draw_cluster_section(self, stdscr, y: int) -> int:
        """Draw cluster nodes section"""
        y = self._draw_header(stdscr, y, "CLUSTER NODES")
        
        nodes = self.cluster_health.get("nodes", {})
        if not nodes:
            stdscr.addstr(y, 2, "No nodes available", curses.color_pair(Colors.WARNING))
            return y + 2
        
        # Header
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y, 2, "Node".ljust(15), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 17, "Status".ljust(10), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 27, "CPU".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 35, "GPU".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 43, "Latency (ms)".ljust(20), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 63, "Model".ljust(25), curses.color_pair(Colors.INFO))
        stdscr.attroff(curses.A_BOLD)
        y += 1
        
        # Nodes
        for node, info in list(nodes.items())[:8]:  # Max 8 nodes
            online = info.get("online", False)
            status = "online" if online else "offline"
            status_color = Colors.OK if online else Colors.CRITICAL
            
            stdscr.addstr(y, 2, node[:14].ljust(15))
            stdscr.addstr(y, 17, status.ljust(10), curses.color_pair(status_color))
            stdscr.addstr(y, 27, f"{info.get('cpu', 'N/A')}%".ljust(8))
            stdscr.addstr(y, 35, f"{info.get('gpu', 'N/A')}%".ljust(8))
            stdscr.addstr(y, 43, str(info.get('latency_ms', 0)).ljust(20))
            stdscr.addstr(y, 63, info.get('model', 'N/A')[:24].ljust(25))
            y += 1
        
        return y + 1
    
    def _draw_gpu_section(self, stdscr, y: int) -> int:
        """Draw GPU statistics section"""
        y = self._draw_header(stdscr, y, "GPU STATISTICS")
        
        gpus = self.gpu_stats.get("gpus", [])
        if not gpus:
            stdscr.addstr(y, 2, "No GPU data available", curses.color_pair(Colors.WARNING))
            return y + 2
        
        # Header
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y, 2, "GPU".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 10, "Util".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 18, "Memory".ljust(10), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 28, "Temp".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 36, "Power".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 44, "Trend".ljust(20), curses.color_pair(Colors.INFO))
        stdscr.attroff(curses.A_BOLD)
        y += 1
        
        # GPU rows
        for gpu in gpus[:6]:  # Max 6 GPUs
            gpu_idx = gpu.get("index", "?")
            util = gpu.get("utilization", 0)
            memory = gpu.get("memory_used", 0)
            temp = gpu.get("temperature", 0)
            power = gpu.get("power_draw", 0)
            
            util_color = Colors.OK if util < 70 else Colors.WARNING if util < 90 else Colors.CRITICAL
            temp_color = Colors.OK if temp < 70 else Colors.WARNING if temp < 85 else Colors.CRITICAL
            
            stdscr.addstr(y, 2, f"GPU{gpu_idx}".ljust(8))
            stdscr.addstr(y, 10, f"{util}%".ljust(8), curses.color_pair(util_color))
            stdscr.addstr(y, 18, f"{memory}MB".ljust(10))
            stdscr.addstr(y, 28, f"{temp}°C".ljust(8), curses.color_pair(temp_color))
            stdscr.addstr(y, 36, f"{power}W".ljust(8))
            stdscr.addstr(y, 44, self._sparkline(list(self.gpu_temp_history)[-20:], 20))
            y += 1
        
        return y + 1
    
    def _draw_trading_section(self, stdscr, y: int) -> int:
        """Draw trading section"""
        y = self._draw_header(stdscr, y, "TRADING POSITIONS")
        
        positions = self.trading_data.get("positions", [])
        if not positions:
            stdscr.addstr(y, 2, "No open positions", curses.color_pair(Colors.INFO))
            return y + 2
        
        # Header
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y, 2, "Symbol".ljust(12), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 14, "Entry".ljust(12), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 26, "Current".ljust(12), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 38, "PnL".ljust(10), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 48, "Qty".ljust(10), curses.color_pair(Colors.INFO))
        stdscr.attroff(curses.A_BOLD)
        y += 1
        
        # Positions
        for pos in positions[:5]:  # Max 5 positions
            symbol = pos.get("symbol", "?")
            entry = pos.get("entry_price", 0)
            current = pos.get("current_price", 0)
            pnl = pos.get("pnl_pct", 0)
            qty = pos.get("quantity", 0)
            
            pnl_color = Colors.OK if pnl >= 0 else Colors.CRITICAL
            
            stdscr.addstr(y, 2, symbol[:11].ljust(12))
            stdscr.addstr(y, 14, f"{entry:.2f}".ljust(12))
            stdscr.addstr(y, 26, f"{current:.2f}".ljust(12))
            stdscr.addstr(y, 38, f"{pnl:+.1f}%".ljust(10), curses.color_pair(pnl_color))
            stdscr.addstr(y, 48, f"{qty}".ljust(10))
            y += 1
        
        return y + 1
    
    def _draw_agents_section(self, stdscr, y: int) -> int:
        """Draw active agents section"""
        y = self._draw_header(stdscr, y, "ACTIVE AGENTS")
        
        agents = self.agents.get("agents", [])
        if not agents:
            stdscr.addstr(y, 2, "No active agents", curses.color_pair(Colors.INFO))
            return y + 2
        
        # Header
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(y, 2, "Agent".ljust(20), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 22, "Status".ljust(12), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 34, "CPU".ljust(8), curses.color_pair(Colors.INFO))
        stdscr.addstr(y, 42, "Memory".ljust(12), curses.color_pair(Colors.INFO))
        stdscr.attroff(curses.A_BOLD)
        y += 1
        
        # Agents
        for agent in agents[:6]:  # Max 6 agents
            name = agent.get("name", "?")
            status = agent.get("status", "unknown")
            cpu = agent.get("cpu_usage", 0)
            memory = agent.get("memory_mb", 0)
            
            status_color = Colors.OK if status == "running" else Colors.WARNING
            
            stdscr.addstr(y, 2, name[:19].ljust(20))
            stdscr.addstr(y, 22, status[:11].ljust(12), curses.color_pair(status_color))
            stdscr.addstr(y, 34, f"{cpu}%".ljust(8))
            stdscr.addstr(y, 42, f"{memory}MB".ljust(12))
            y += 1
        
        return y + 1
    
    def _draw_footer(self, stdscr, y: int):
        """Draw status footer"""
        height, width = stdscr.getmaxyx()
        
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        nodes_online = len([n for n in self.cluster_health.get("nodes", {}).values() if n.get("online")])
        status_text = f"Uptime: {uptime_str} | Nodes: {nodes_online} | Updated: {self.last_update.strftime('%H:%M:%S')}"
        
        stdscr.attron(curses.A_REVERSE)
        stdscr.addstr(height - 2, 0, status_text.ljust(width))
        stdscr.attroff(curses.A_REVERSE)
        
        help_text = "q:quit | r:refresh | t:trading | c:cluster | g:gpu"
        stdscr.addstr(height - 1, 0, help_text.ljust(width), curses.color_pair(Colors.DIM))
    
    def run(self, stdscr):
        """Main dashboard loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(True)  # Non-blocking input
        
        # Start data fetch thread
        fetch_thread = threading.Thread(target=self._update_data, daemon=True)
        fetch_thread.start()
        
        selected_tab = "all"  # all, cluster, trading, agents
        
        while self.running:
            try:
                stdscr.clear()
                height, width = stdscr.getmaxyx()
                
                y = 1
                
                if selected_tab in ("all", "cluster"):
                    y = self._draw_cluster_section(stdscr, y)
                
                if selected_tab in ("all", "gpu"):
                    y = self._draw_gpu_section(stdscr, y)
                
                if selected_tab in ("all", "trading"):
                    y = self._draw_trading_section(stdscr, y)
                
                if selected_tab == "all":
                    y = self._draw_agents_section(stdscr, y)
                
                self._draw_footer(stdscr, height)
                stdscr.refresh()
                
                # Handle input
                try:
                    ch = stdscr.getch()
                    if ch == ord('q'):
                        self.running = False
                    elif ch == ord('r'):
                        pass  # Force refresh
                    elif ch == ord('t'):
                        selected_tab = "trading" if selected_tab != "trading" else "all"
                    elif ch == ord('c'):
                        selected_tab = "cluster" if selected_tab != "cluster" else "all"
                    elif ch == ord('g'):
                        selected_tab = "gpu" if selected_tab != "gpu" else "all"
                except:
                    pass
                
                time.sleep(self.update_interval)
            
            except curses.error:
                pass
            except KeyboardInterrupt:
                self.running = False


def main():
    """Main entry point"""
    import sys
    
    try:
        curses.wrapper(Dashboard().run)
    except KeyboardInterrupt:
        print("Dashboard stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
