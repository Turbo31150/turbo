// VoiceConsoleWidget.tsx - Console commandes vocales - Waveform + historique
import { useState, useEffect, useRef, useCallback } from 'react';

interface VoiceCommand { id: number; text: string; confidence: number; category: string; timestamp: number; latencyMs: number; recognized: boolean; }
interface VoiceStats { totalCommands: number; totalCategories: number; avgConfidence: number; avgLatencyMs: number; commandsPerMin: number; recognitionRate: number; }

function WaveformCanvas({ active }: { active: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const barsRef = useRef<number[]>(Array(64).fill(0));
  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const ctx = canvas.getContext('2d'); if (!ctx) return;
    const draw = () => {
      const { width, height } = canvas; ctx.clearRect(0, 0, width, height);
      const bars = barsRef.current; const barW = width / bars.length; const now = Date.now() / 1000;
      for (let i = 0; i < bars.length; i++) {
        if (active) { const target = Math.random() * 0.8 + 0.2; bars[i] += (target - bars[i]) * 0.3; }
        else { bars[i] = 0.05 + 0.03 * Math.sin(now * 2 + i * 0.3); }
        const h = bars[i] * height * 0.8; const x = i * barW; const y = (height - h) / 2;
        const gradient = ctx.createLinearGradient(x, y, x, y + h);
        if (active) { gradient.addColorStop(0, '#00ff9f'); gradient.addColorStop(0.5, '#00d4ff'); gradient.addColorStop(1, '#a855f7'); }
        else { gradient.addColorStop(0, '#1e293b'); gradient.addColorStop(1, '#334155'); }
        ctx.fillStyle = gradient; ctx.fillRect(x + 1, y, barW - 2, h);
      }
      animRef.current = requestAnimationFrame(draw);
    };
    draw(); return () => cancelAnimationFrame(animRef.current);
  }, [active]);
  return <canvas ref={canvasRef} width={512} height={80} className="w-full h-16 rounded-lg bg-black/40" />;
}

export default function VoiceConsoleWidget() {
  const [commands, setCommands] = useState<VoiceCommand[]>([]);
  const [stats, setStats] = useState<VoiceStats>({ totalCommands: 2182, totalCategories: 84, avgConfidence: 0.89, avgLatencyMs: 340, commandsPerMin: 2.4, recognitionRate: 0.94 });
  const [listening, setListening] = useState(false);
  const [currentText, setCurrentText] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const connect = useCallback(() => {
    const ws = new WebSocket('ws://127.0.0.1:9742/voice'); wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'voice_active') { setListening(data.active); setCurrentText(data.partialText || ''); }
        if (data.type === 'voice_command') { setCommands(prev => { const next = [...prev, data.command]; return next.length > 500 ? next.slice(-300) : next; }); setCurrentText(''); }
        if (data.type === 'voice_stats') setStats(data.stats);
      } catch {}
    };
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000); };
    ws.onerror = () => ws.close();
  }, []);
  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' }); }, [commands.length]);
  const categories = [...new Set(commands.map(c => c.category))].sort();
  const filteredCommands = selectedCategory ? commands.filter(c => c.category === selectedCategory) : commands;
  return (
    <div className="bg-gray-950/90 rounded-xl border border-green-900/30 p-4 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><span className="text-lg">🎙️</span><h2 className="text-base font-bold font-mono text-green-300">VOICE CONSOLE</h2></div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="text-gray-500">{stats.totalCommands} cmds · {stats.totalCategories} cat</span>
          <div className={`flex items-center gap-1 ${listening ? 'text-green-400' : connected ? 'text-gray-500' : 'text-red-400'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${listening ? 'bg-green-400 animate-pulse' : connected ? 'bg-gray-500' : 'bg-red-500'}`} />
            {listening ? 'LISTENING' : connected ? 'IDLE' : 'OFFLINE'}
          </div>
        </div>
      </div>
      <WaveformCanvas active={listening} />
      {currentText && <div className="mt-2 px-3 py-2 bg-green-500/10 border border-green-500/30 rounded-lg"><span className="text-xs font-mono text-green-300 animate-pulse">⟫ {currentText}</span></div>}
      <div className="grid grid-cols-4 gap-2 mt-3 mb-3">
        {[{ label: 'Reco Rate', value: `${Math.round(stats.recognitionRate * 100)}%`, color: 'text-emerald-400' }, { label: 'Avg Conf', value: `${Math.round(stats.avgConfidence * 100)}%`, color: 'text-cyan-400' }, { label: 'Latency', value: `${stats.avgLatencyMs}ms`, color: 'text-yellow-400' }, { label: 'Cmd/min', value: stats.commandsPerMin.toFixed(1), color: 'text-purple-400' }].map(s => (
          <div key={s.label} className="text-center bg-gray-900/50 rounded-lg py-1.5"><div className="text-[9px] font-mono text-gray-500">{s.label}</div><div className={`text-sm font-bold font-mono ${s.color}`}>{s.value}</div></div>
        ))}
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        <button onClick={() => setSelectedCategory(null)} className={`px-2 py-0.5 text-[9px] font-mono rounded ${!selectedCategory ? 'bg-green-600/30 text-green-300' : 'text-gray-600 hover:text-gray-300'}`}>ALL ({commands.length})</button>
        {categories.slice(0, 12).map(cat => <button key={cat} onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)} className={`px-2 py-0.5 text-[9px] font-mono rounded ${selectedCategory === cat ? 'bg-green-600/30 text-green-300' : 'text-gray-600 hover:text-gray-300'}`}>{cat} ({commands.filter(c => c.category === cat).length})</button>)}
      </div>
      <div ref={listRef} className="bg-black/40 rounded-lg border border-gray-800/50 p-2 h-40 overflow-y-auto">
        {filteredCommands.length === 0 ? <div className="text-center text-gray-600 font-mono text-xs py-6">En attente de commandes vocales...</div> :
          filteredCommands.slice(-100).map(cmd => (
            <div key={cmd.id} className={`flex items-center gap-2 py-1 px-1 rounded hover:bg-white/5 ${!cmd.recognized ? 'opacity-50' : ''}`}>
              <span className="text-[9px] font-mono text-gray-700 shrink-0">{new Date(cmd.timestamp).toLocaleTimeString()}</span>
              <span className="text-[10px] font-mono text-gray-200 flex-1 truncate">{cmd.recognized ? '✓' : '✗'} {cmd.text}</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold ${cmd.confidence >= 0.8 ? 'text-emerald-400 bg-emerald-500/20' : cmd.confidence >= 0.6 ? 'text-yellow-400 bg-yellow-500/20' : 'text-red-400 bg-red-500/20'}`}>{Math.round(cmd.confidence * 100)}%</span>
              <span className="text-[9px] font-mono text-gray-600 shrink-0">{cmd.latencyMs}ms</span>
            </div>
          ))}
      </div>
    </div>
  );
}