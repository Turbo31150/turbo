// ClusterHeatmapWidget.tsx - Heatmap topologique cluster 3 machines + Ollama
import { useState, useEffect, useRef, useCallback } from 'react';

interface NodeHealth { id: string; name: string; type: 'lmstudio' | 'ollama' | 'cloud'; ip: string; port: number; status: 'online' | 'offline' | 'degraded' | 'overloaded'; cpuPercent: number; gpuPercent: number; gpuTempAvg: number; vramUsedGB: number; vramTotalGB: number; latencyMs: number; tokensPerSec: number; activeRequests: number; modelsLoaded: string[]; uptime: number; lastPing: number; }
interface MachineGroup { machine: string; label: string; gpuCount: number; nodes: NodeHealth[]; }

function healthColor(status: string): string { switch (status) { case 'online': return '#00ff9f'; case 'degraded': return '#f5e642'; case 'overloaded': return '#ff8c00'; default: return '#ff003c'; } }
function heatColor(value: number): string { const r = value/100; if (r < 0.4) return 'bg-emerald-500/30'; if (r < 0.6) return 'bg-emerald-500/50'; if (r < 0.75) return 'bg-yellow-500/40'; if (r < 0.85) return 'bg-orange-500/40'; return 'bg-red-500/50 animate-pulse'; }
function formatUptime(s: number): string { const h = Math.floor(s/3600); const m = Math.floor((s%3600)/60); return h > 0 ? `${h}h${m}m` : `${m}m`; }

function NodeCell({ node, onHover, onLeave }: { node: NodeHealth; onHover: (n: NodeHealth, e: React.MouseEvent) => void; onLeave: () => void }) {
  const isOffline = node.status === 'offline';
  return (
    <div onMouseEnter={e => onHover(node, e)} onMouseLeave={onLeave} className={`relative rounded-lg border p-2 cursor-pointer transition-all duration-300 ${isOffline ? 'bg-gray-900/50 border-gray-800/30 opacity-50' : `${heatColor(node.gpuPercent)} border-gray-700/40 hover:border-cyan-500/50`}`}>
      <div className="absolute top-1 right-1"><div className={`w-2 h-2 rounded-full ${node.status === 'online' ? 'animate-pulse' : ''}`} style={{ backgroundColor: healthColor(node.status) }} /></div>
      <div className="text-[10px] font-mono font-bold text-gray-200 truncate mb-1">{node.name}</div>
      <div className="grid grid-cols-2 gap-x-2 text-[8px] font-mono text-gray-400"><span>GPU {node.gpuPercent}%</span><span>CPU {node.cpuPercent}%</span><span>{node.gpuTempAvg}°C</span><span>{node.latencyMs}ms</span></div>
      <div className="mt-1 h-1 bg-gray-800 rounded-full overflow-hidden"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${node.vramTotalGB > 0 ? (node.vramUsedGB/node.vramTotalGB)*100 : 0}%`, background: 'linear-gradient(90deg, #00ff9f, #00d4ff)' }} /></div>
      <div className="text-[8px] font-mono text-gray-600 mt-0.5">{node.modelsLoaded.length} model{node.modelsLoaded.length !== 1 ? 's' : ''}</div>
    </div>
  );
}

function TooltipBox({ node, position }: { node: NodeHealth; position: { x: number; y: number } }) {
  const vramPct = node.vramTotalGB > 0 ? Math.round((node.vramUsedGB/node.vramTotalGB)*100) : 0;
  return (
    <div className="fixed z-50 bg-gray-900 border border-cyan-800/50 rounded-lg shadow-2xl p-3 max-w-xs pointer-events-none" style={{ left: position.x + 12, top: position.y - 10 }}>
      <div className="flex items-center gap-2 mb-2"><div className="w-2 h-2 rounded-full" style={{ backgroundColor: healthColor(node.status) }} /><span className="text-xs font-mono font-bold text-cyan-300">{node.name}</span><span className="text-[9px] font-mono text-gray-500 uppercase">{node.status}</span></div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] font-mono">
        <div className="text-gray-500">IP</div><div className="text-gray-300">{node.ip}:{node.port}</div>
        <div className="text-gray-500">GPU</div><div className="text-gray-300">{node.gpuPercent}%</div>
        <div className="text-gray-500">VRAM</div><div className="text-gray-300">{node.vramUsedGB.toFixed(1)}/{node.vramTotalGB.toFixed(1)} GB ({vramPct}%)</div>
        <div className="text-gray-500">Latency</div><div className="text-gray-300">{node.latencyMs}ms</div>
        <div className="text-gray-500">Throughput</div><div className="text-gray-300">{node.tokensPerSec} tok/s</div>
        <div className="text-gray-500">Uptime</div><div className="text-gray-300">{formatUptime(node.uptime)}</div>
      </div>
      {node.modelsLoaded.length > 0 && <div className="mt-2 pt-2 border-t border-gray-800"><div className="text-[9px] font-mono text-gray-500 mb-1">Models:</div><div className="flex flex-wrap gap-1">{node.modelsLoaded.map(m => <span key={m} className="px-1.5 py-0.5 bg-cyan-500/10 text-cyan-400 rounded text-[8px] font-mono">{m}</span>)}</div></div>}
    </div>
  );
}

export default function ClusterHeatmapWidget() {
  const [groups, setGroups] = useState<MachineGroup[]>([]);
  const [connected, setConnected] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<NodeHealth | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const wsRef = useRef<WebSocket | null>(null);
  const connect = useCallback(() => {
    const ws = new WebSocket('ws://127.0.0.1:9742/cluster'); wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => { try { setGroups(JSON.parse(event.data)); } catch {} };
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000); };
    ws.onerror = () => ws.close();
  }, []);
  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);
  const allNodes = groups.flatMap(g => g.nodes);
  const totalOnline = allNodes.filter(n => n.status !== 'offline').length;
  const totalModels = new Set(allNodes.flatMap(n => n.modelsLoaded)).size;
  return (
    <div className="bg-gray-950/90 rounded-xl border border-amber-900/30 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><span className="text-lg">🌐</span><h2 className="text-base font-bold font-mono text-amber-300">CLUSTER HEATMAP</h2></div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="text-gray-500">{totalOnline} nodes · {totalModels} models</span>
          <div className={`flex items-center gap-1 ${connected ? 'text-emerald-400' : 'text-red-400'}`}><div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />{connected ? 'LIVE' : 'OFFLINE'}</div>
        </div>
      </div>
      {groups.length === 0 ? <div className="text-center py-8 text-gray-600 font-mono text-sm">{connected ? 'En attente...' : 'Connexion ws://127.0.0.1:9742/cluster...'}</div> :
        groups.map(group => (
          <div key={group.machine} className="mb-3">
            <div className="flex items-center gap-2 mb-1.5"><span className="text-[10px] font-mono font-bold text-gray-300">{group.label}</span><span className="text-[9px] font-mono text-gray-600">{group.gpuCount} GPU · {group.nodes.filter(n => n.status !== 'offline').length}/{group.nodes.length} online</span></div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">{group.nodes.map(node => <NodeCell key={node.id} node={node} onHover={(n, e) => { setHoveredNode(n); setTooltipPos({ x: e.clientX, y: e.clientY }); }} onLeave={() => setHoveredNode(null)} />)}</div>
          </div>
        ))}
      {hoveredNode && <TooltipBox node={hoveredNode} position={tooltipPos} />}
    </div>
  );
}