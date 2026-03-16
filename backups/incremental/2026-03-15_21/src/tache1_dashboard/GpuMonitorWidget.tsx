// GpuMonitorWidget.tsx - Monitoring GPU temps réel via WebSocket port 9742
// Stack: React 19, TypeScript, TailwindCSS, Recharts, WebSocket natif
// Dark theme cyberpunk - Refresh 2s

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';

// --- Types ---
interface GpuData {
  id: string;
  name: string;
  temperature: number;
  vramUsed: number;
  vramTotal: number;
  utilization: number;
  fanSpeed: number;
  powerDraw: number;
}

interface MachineData {
  machine: string;
  ip: string;
  gpus: GpuData[];
  timestamp: number;
}

interface SparkPoint {
  time: number;
  temp: number;
  vram: number;
  util: number;
}

type HistoryMap = Record<string, SparkPoint[]>;

// --- Helpers ---
const MAX_HISTORY = 60;

function tempColor(t: number): string {
  if (t < 60) return '#00ff9f';
  if (t < 75) return '#f5e642';
  if (t < 85) return '#ff8c00';
  return '#ff003c';
}

function tempBg(t: number): string {
  if (t < 60) return 'bg-emerald-500/20 border-emerald-400/50';
  if (t < 75) return 'bg-yellow-500/20 border-yellow-400/50';
  if (t < 85) return 'bg-orange-500/20 border-orange-400/50';
  return 'bg-red-500/20 border-red-400/50 animate-pulse';
}

function vramPercent(used: number, total: number): number {
  return total > 0 ? Math.round((used / total) * 100) : 0;
}

// --- Sub-components ---
function GpuCard({ gpu, history }: { gpu: GpuData; history: SparkPoint[] }) {
  const pct = vramPercent(gpu.vramUsed, gpu.vramTotal);
  const color = tempColor(gpu.temperature);

  return (
    <div className={`rounded-lg border p-3 ${tempBg(gpu.temperature)} backdrop-blur-sm transition-all duration-300`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-cyan-300 truncate max-w-[140px]">{gpu.name}</span>
        <span className="text-lg font-bold font-mono" style={{ color }}>
          {gpu.temperature}°C
        </span>
      </div>
      <div className="h-12 mb-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history}>
            <defs>
              <linearGradient id={`grad-${gpu.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone" dataKey="temp" stroke={color} strokeWidth={1.5}
              fill={`url(#grad-${gpu.id})`} isAnimationActive={false}
            />
            <YAxis domain={[20, 100]} hide />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="mb-1">
        <div className="flex justify-between text-[10px] font-mono text-gray-400 mb-0.5">
          <span>VRAM</span>
          <span>{gpu.vramUsed.toFixed(1)} / {gpu.vramTotal.toFixed(1)} GB ({pct}%)</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: `linear-gradient(90deg, #00ff9f, ${pct > 80 ? '#ff003c' : '#00d4ff'})`
            }}
          />
        </div>
      </div>
      <div className="flex justify-between text-[10px] font-mono text-gray-500 mt-1">
        <span>GPU: {gpu.utilization}%</span>
        <span>Fan: {gpu.fanSpeed}%</span>
        <span>{gpu.powerDraw}W</span>
      </div>
    </div>
  );
}

function MachineSection({ machine, history }: { machine: MachineData; history: HistoryMap }) {
  const totalVram = machine.gpus.reduce((s, g) => s + g.vramTotal, 0);
  const usedVram = machine.gpus.reduce((s, g) => s + g.vramUsed, 0);
  const avgTemp = machine.gpus.length > 0
    ? Math.round(machine.gpus.reduce((s, g) => s + g.temperature, 0) / machine.gpus.length)
    : 0;

  return (
    <div className="mb-4">
      <div className="flex items-center gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <h3 className="text-sm font-bold font-mono text-cyan-300">{machine.machine}</h3>
        </div>
        <span className="text-[10px] font-mono text-gray-500">{machine.ip}</span>
        <div className="flex-1" />
        <span className="text-[10px] font-mono text-gray-400">
          {machine.gpus.length} GPU · {avgTemp}°C avg · {usedVram.toFixed(1)}/{totalVram.toFixed(1)} GB
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {machine.gpus.map((gpu) => (
          <GpuCard key={gpu.id} gpu={gpu} history={history[gpu.id] || []} />
        ))}
      </div>
    </div>
  );
}

// --- Main Widget ---
export default function GpuMonitorWidget() {
  const [machines, setMachines] = useState<MachineData[]>([]);
  const [history, setHistory] = useState<HistoryMap>({});
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket('ws://127.0.0.1:9742/gpu');
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
    ws.onmessage = (event) => {
      try {
        const data: MachineData[] = JSON.parse(event.data);
        setMachines(data);
        setLastUpdate(new Date());
        setHistory((prev) => {
          const next = { ...prev };
          const now = Date.now();
          for (const machine of data) {
            for (const gpu of machine.gpus) {
              const arr = [...(next[gpu.id] || [])];
              arr.push({ time: now, temp: gpu.temperature, vram: vramPercent(gpu.vramUsed, gpu.vramTotal), util: gpu.utilization });
              if (arr.length > MAX_HISTORY) arr.shift();
              next[gpu.id] = arr;
            }
          }
          return next;
        });
      } catch { /* ignore */ }
    };
    ws.onclose = () => {
      setConnected(false);
      reconnectRef.current = setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  const totalGpus = machines.reduce((s, m) => s + m.gpus.length, 0);
  const totalVram = machines.reduce((s, m) => s + m.gpus.reduce((v, g) => v + g.vramTotal, 0), 0);

  return (
    <div className="bg-gray-950/90 rounded-xl border border-cyan-900/30 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">🖥️</span>
          <h2 className="text-base font-bold font-mono text-cyan-300">GPU MONITOR</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-gray-500">{totalGpus} GPUs · {totalVram.toFixed(0)} GB</span>
          <div className={`flex items-center gap-1 text-[10px] font-mono ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            {connected ? 'LIVE' : 'DISCONNECTED'}
          </div>
          {lastUpdate && (
            <span className="text-[10px] font-mono text-gray-600">{lastUpdate.toLocaleTimeString()}</span>
          )}
        </div>
      </div>
      {machines.length === 0 ? (
        <div className="text-center py-8 text-gray-600 font-mono text-sm">
          {connected ? 'En attente des données GPU...' : 'Connexion à ws://127.0.0.1:9742/gpu...'}
        </div>
      ) : (
        machines.map((m) => <MachineSection key={m.machine} machine={m} history={history} />)
      )}
    </div>
  );
}