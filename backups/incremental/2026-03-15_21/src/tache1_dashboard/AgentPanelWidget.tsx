// AgentPanelWidget.tsx - Panel contrôle 7 agents Claude SDK
// Stack: React 19, TypeScript, TailwindCSS, WebSocket natif

import { useState, useEffect, useRef, useCallback } from 'react';

type AgentStatus = 'running' | 'stopped' | 'starting' | 'error' | 'stopping';

interface AgentInfo {
  id: string; name: string; description: string; status: AgentStatus;
  tokensUsed: number; tokensPerMin: number; startedAt: number | null;
  lastActivity: number | null; errorCount: number; tasksCompleted: number;
}

interface LogEntry { timestamp: number; agentId: string; level: 'info' | 'warn' | 'error' | 'debug'; message: string; }

const AGENTS_DEF = [
  { id: 'ia-deep', name: 'IA Deep', description: 'Analyse approfondie (poids 1.3)' },
  { id: 'ia-fast', name: 'IA Fast', description: 'Réponse rapide (poids 1.0)' },
  { id: 'ia-check', name: 'IA Check', description: 'Validateur cross-check (poids 0.8)' },
  { id: 'ia-trading', name: 'IA Trading', description: 'Signaux & scan sniper' },
  { id: 'ia-system', name: 'IA System', description: 'Monitoring système & cluster' },
  { id: 'ia-bridge', name: 'IA Bridge', description: 'Routage intelligent multi-noeud' },
  { id: 'ia-consensus', name: 'IA Consensus', description: 'Agrégation consensus multi-IA' },
];

const STATUS_STYLES: Record<AgentStatus, { dot: string; text: string; label: string }> = {
  running:  { dot: 'bg-emerald-400 animate-pulse', text: 'text-emerald-400', label: 'RUNNING' },
  stopped:  { dot: 'bg-red-500', text: 'text-red-400', label: 'STOPPED' },
  starting: { dot: 'bg-yellow-400 animate-pulse', text: 'text-yellow-400', label: 'STARTING' },
  stopping: { dot: 'bg-yellow-400', text: 'text-yellow-400', label: 'STOPPING' },
  error:    { dot: 'bg-red-500 animate-pulse', text: 'text-red-400', label: 'ERROR' },
};

function formatDuration(startMs: number | null): string {
  if (!startMs) return '--:--:--';
  const diff = Math.floor((Date.now() - startMs) / 1000);
  return `${Math.floor(diff/3600).toString().padStart(2,'0')}:${Math.floor((diff%3600)/60).toString().padStart(2,'0')}:${(diff%60).toString().padStart(2,'0')}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n/1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n/1_000).toFixed(1) + 'K';
  return n.toString();
}

function AgentCard({ agent, onStart, onStop }: { agent: AgentInfo; onStart: () => void; onStop: () => void }) {
  const style = STATUS_STYLES[agent.status];
  const isRunning = agent.status === 'running';
  const isBusy = agent.status === 'starting' || agent.status === 'stopping';
  return (
    <div className={`rounded-lg border p-3 backdrop-blur-sm transition-all duration-300 ${isRunning ? 'bg-emerald-500/5 border-emerald-800/40' : 'bg-gray-900/50 border-gray-800/40'}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${style.dot}`} />
          <span className="text-sm font-bold font-mono text-gray-200">{agent.name}</span>
        </div>
        <span className={`text-[10px] font-mono font-bold ${style.text}`}>{style.label}</span>
      </div>
      <p className="text-[10px] text-gray-500 mb-2 font-mono">{agent.description}</p>
      <div className="grid grid-cols-3 gap-1 mb-2 text-[10px] font-mono">
        <div className="text-center"><div className="text-gray-500">Tokens</div><div className="text-cyan-300 font-bold">{formatTokens(agent.tokensUsed)}</div></div>
        <div className="text-center"><div className="text-gray-500">tok/min</div><div className="text-cyan-300 font-bold">{agent.tokensPerMin}</div></div>
        <div className="text-center"><div className="text-gray-500">Durée</div><div className="text-cyan-300 font-bold">{formatDuration(agent.startedAt)}</div></div>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-gray-600">✓{agent.tasksCompleted} ✗{agent.errorCount}</span>
        {isRunning ? (
          <button onClick={onStop} disabled={isBusy} className="px-3 py-1 text-[10px] font-mono font-bold rounded bg-red-600/20 border border-red-600/50 text-red-400 hover:bg-red-600/40 transition-colors disabled:opacity-50">STOP</button>
        ) : (
          <button onClick={onStart} disabled={isBusy} className="px-3 py-1 text-[10px] font-mono font-bold rounded bg-emerald-600/20 border border-emerald-600/50 text-emerald-400 hover:bg-emerald-600/40 transition-colors disabled:opacity-50">START</button>
        )}
      </div>
    </div>
  );
}

function LogTerminal({ logs, filter }: { logs: LogEntry[]; filter: string | null }) {
  const endRef = useRef<HTMLDivElement>(null);
  const filtered = filter ? logs.filter(l => l.agentId === filter) : logs;
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [filtered.length]);
  const LOG_COLORS: Record<string,string> = { info: 'text-cyan-400', warn: 'text-yellow-400', error: 'text-red-400', debug: 'text-gray-500' };
  return (
    <div className="bg-black/60 rounded-lg border border-gray-800/50 p-2 h-48 overflow-y-auto font-mono text-[10px]">
      {filtered.length === 0 ? <div className="text-gray-600 text-center py-4">Aucun log</div> :
        filtered.slice(-200).map((log, i) => (
          <div key={i} className="flex gap-2 leading-relaxed hover:bg-white/5">
            <span className="text-gray-700 shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
            <span className="text-purple-400 shrink-0 w-20 truncate">[{log.agentId}]</span>
            <span className={LOG_COLORS[log.level] || 'text-gray-400'}>{log.message}</span>
          </div>
        ))}
      <div ref={endRef} />
    </div>
  );
}

export default function AgentPanelWidget() {
  const [agents, setAgents] = useState<AgentInfo[]>(AGENTS_DEF.map(a => ({ ...a, status: 'stopped' as AgentStatus, tokensUsed: 0, tokensPerMin: 0, startedAt: null, lastActivity: null, errorCount: 0, tasksCompleted: 0 })));
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logFilter, setLogFilter] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = useCallback((agentId: string, level: LogEntry['level'], message: string) => {
    setLogs(prev => { const next = [...prev, { timestamp: Date.now(), agentId, level, message }]; return next.length > 1000 ? next.slice(-500) : next; });
  }, []);

  const connect = useCallback(() => {
    const ws = new WebSocket('ws://127.0.0.1:9742/agents');
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'agent_status') setAgents(prev => prev.map(a => a.id === data.agentId ? { ...a, ...data.update } : a));
        if (data.type === 'agent_log') addLog(data.agentId, data.level, data.message);
      } catch {}
    };
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000); };
    ws.onerror = () => ws.close();
  }, [addLog]);

  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);

  const sendCommand = (agentId: string, command: 'start' | 'stop') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'agent_command', agentId, command }));
      setAgents(prev => prev.map(a => a.id === agentId ? { ...a, status: command === 'start' ? 'starting' : 'stopping' } : a));
      addLog(agentId, 'info', `${command === 'start' ? 'Démarrage' : 'Arrêt'} demandé...`);
    }
  };

  const runningCount = agents.filter(a => a.status === 'running').length;
  const totalTokens = agents.reduce((s, a) => s + a.tokensUsed, 0);

  return (
    <div className="bg-gray-950/90 rounded-xl border border-purple-900/30 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><span className="text-lg">🤖</span><h2 className="text-base font-bold font-mono text-purple-300">AGENTS PANEL</h2></div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="text-gray-500">{runningCount}/7 actifs · {formatTokens(totalTokens)} tokens</span>
          <div className={`flex items-center gap-1 ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            {connected ? 'WS OK' : 'OFFLINE'}
          </div>
        </div>
      </div>
      <div className="flex gap-2 mb-3">
        <button onClick={() => agents.filter(a => a.status === 'stopped').forEach(a => sendCommand(a.id, 'start'))} className="px-2 py-1 text-[10px] font-mono rounded bg-emerald-600/20 border border-emerald-600/40 text-emerald-400 hover:bg-emerald-600/40">▶ START ALL</button>
        <button onClick={() => agents.filter(a => a.status === 'running').forEach(a => sendCommand(a.id, 'stop'))} className="px-2 py-1 text-[10px] font-mono rounded bg-red-600/20 border border-red-600/40 text-red-400 hover:bg-red-600/40">■ STOP ALL</button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2 mb-3">
        {agents.map(agent => <AgentCard key={agent.id} agent={agent} onStart={() => sendCommand(agent.id, 'start')} onStop={() => sendCommand(agent.id, 'stop')} />)}
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-mono text-gray-500">LOGS:</span>
        <button onClick={() => setLogFilter(null)} className={`px-2 py-0.5 text-[10px] font-mono rounded ${!logFilter ? 'bg-purple-600/30 text-purple-300' : 'text-gray-500 hover:text-gray-300'}`}>ALL</button>
        {agents.map(a => <button key={a.id} onClick={() => setLogFilter(a.id)} className={`px-2 py-0.5 text-[10px] font-mono rounded ${logFilter === a.id ? 'bg-purple-600/30 text-purple-300' : 'text-gray-600 hover:text-gray-300'}`}>{a.name.replace('IA ', '')}</button>)}
      </div>
      <LogTerminal logs={logs} filter={logFilter} />
    </div>
  );
}