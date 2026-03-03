import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useWebSocket, WsMessage } from '../hooks/useWebSocket';
import { COLORS, FONT } from '../lib/theme';

interface LogEntry {
  id: number;
  ts: string;
  channel: string;
  type: string;
  action?: string;
  event?: string;
  preview: string;
}

const CHANNELS = ['cluster', 'trading', 'voice', 'chat', 'system', 'files', 'dictionary'] as const;

const CHANNEL_COLORS: Record<string, string> = {
  cluster: COLORS.green,
  trading: COLORS.amber,
  voice: COLORS.purple,
  chat: COLORS.blue,
  system: COLORS.textDim,
  files: COLORS.orange,
  dictionary: COLORS.pink,
};

const S = {
  page: { display: 'flex', flexDirection: 'column', height: '100%', fontFamily: FONT, overflow: 'hidden' } as React.CSSProperties,
  toolbar: { display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderBottom: `1px solid ${COLORS.border}`, flexShrink: 0, backgroundColor: COLORS.bgCard } as React.CSSProperties,
  title: { fontSize: 14, fontWeight: 700, color: COLORS.text, marginRight: 16 } as React.CSSProperties,
  filterBtn: { padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: 'pointer', border: '1px solid transparent', fontFamily: 'inherit', letterSpacing: 0.5, transition: 'all .15s' } as React.CSSProperties,
  logArea: { flex: 1, overflowY: 'auto', padding: '8px 16px', backgroundColor: COLORS.bg } as React.CSSProperties,
  logLine: { display: 'flex', alignItems: 'flex-start', gap: 10, padding: '3px 0', fontSize: 11, lineHeight: 1.5, borderBottom: `1px solid ${COLORS.border}30` } as React.CSSProperties,
  ts: { color: COLORS.textDimmer, fontSize: 10, minWidth: 70, flexShrink: 0, fontVariantNumeric: 'tabular-nums' } as React.CSSProperties,
  channel: { minWidth: 70, fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, flexShrink: 0 } as React.CSSProperties,
  type: { minWidth: 50, fontSize: 10, color: COLORS.textDim, flexShrink: 0 } as React.CSSProperties,
  preview: { color: COLORS.textMuted, fontSize: 11, flex: 1, wordBreak: 'break-all', overflowWrap: 'break-word' } as React.CSSProperties,
  stats: { display: 'flex', gap: 16, padding: '6px 16px', borderTop: `1px solid ${COLORS.border}`, backgroundColor: COLORS.bgCard, fontSize: 10, color: COLORS.textDimmer, flexShrink: 0 } as React.CSSProperties,
  clearBtn: { padding: '4px 12px', borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: 'pointer', border: `1px solid ${COLORS.redAlpha(0.3)}`, backgroundColor: COLORS.redAlpha(0.08), color: COLORS.red, fontFamily: 'inherit', transition: 'all .15s' } as React.CSSProperties,
  pauseBtn: { padding: '4px 12px', borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: 'pointer', border: `1px solid ${COLORS.orangeAlpha(0.3)}`, backgroundColor: COLORS.orangeAlpha(0.08), color: COLORS.orange, fontFamily: 'inherit', transition: 'all .15s' } as React.CSSProperties,
};

const MAX_LOGS = 500;

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set(CHANNELS));
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const idRef = useRef(0);
  const logAreaRef = useRef<HTMLDivElement>(null);
  const { connected, subscribe } = useWebSocket();
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const addLog = useCallback((msg: WsMessage) => {
    if (pausedRef.current) return;
    const entry: LogEntry = {
      id: ++idRef.current,
      ts: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      channel: msg.channel || 'unknown',
      type: msg.type || 'event',
      action: msg.action,
      event: msg.event,
      preview: msg.action || msg.event || (msg.payload ? JSON.stringify(msg.payload).slice(0, 200) : '...'),
    };
    setLogs(prev => {
      const next = [...prev, entry];
      return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
    });
  }, []);

  useEffect(() => {
    const unsubs = CHANNELS.map(ch => subscribe(ch, addLog));
    return () => unsubs.forEach(u => u());
  }, [subscribe, addLog]);

  useEffect(() => {
    if (autoScroll && logAreaRef.current) {
      logAreaRef.current.scrollTop = logAreaRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!logAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logAreaRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  const toggleFilter = (ch: string) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(ch)) next.delete(ch); else next.add(ch);
      return next;
    });
  };

  const filteredLogs = useMemo(() => logs.filter(l => activeFilters.has(l.channel)), [logs, activeFilters]);
  const channelCounts = useMemo(() => logs.reduce<Record<string, number>>((acc, l) => {
    acc[l.channel] = (acc[l.channel] || 0) + 1;
    return acc;
  }, {}), [logs]);

  return (
    <div style={S.page}>
      <div style={S.toolbar}>
        <span style={S.title}>Logs Live</span>
        {CHANNELS.map(ch => {
          const active = activeFilters.has(ch);
          const color = CHANNEL_COLORS[ch] || COLORS.textDim;
          return (
            <button key={ch} aria-pressed={active} style={{
              ...S.filterBtn,
              backgroundColor: active ? `${color}22` : 'transparent',
              color: active ? color : COLORS.textDimmer,
              borderColor: active ? `${color}44` : 'transparent',
            }} onClick={() => toggleFilter(ch)}>
              {ch} {channelCounts[ch] ? `(${channelCounts[ch]})` : ''}
            </button>
          );
        })}
        <div style={{ flex: 1 }} />
        <button style={S.pauseBtn} onClick={() => setPaused(p => !p)} aria-pressed={paused}>
          {paused ? 'RESUME' : 'PAUSE'}
        </button>
        <button style={{ ...S.pauseBtn, borderColor: COLORS.blueAlpha(0.3), backgroundColor: COLORS.blueAlpha(0.08), color: COLORS.blue }}
          onClick={() => {
            const text = filteredLogs.map(l => `${l.ts} [${l.channel}] ${l.type} ${l.preview}`).join('\n');
            const blob = new Blob([text], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `jarvis_logs_${Date.now()}.txt`;
            try {
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
            } finally {
              setTimeout(() => URL.revokeObjectURL(a.href), 1000);
            }
          }}>EXPORT</button>
        <button style={S.clearBtn} onClick={() => setLogs([])}>CLEAR</button>
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {!autoScroll && (
          <button onClick={() => { setAutoScroll(true); if (logAreaRef.current) logAreaRef.current.scrollTop = logAreaRef.current.scrollHeight; }}
            style={{ position: 'absolute', bottom: 12, right: 20, zIndex: 10, padding: '4px 12px', borderRadius: 6, fontSize: 10, fontWeight: 600, cursor: 'pointer', border: `1px solid ${COLORS.blueAlpha(0.3)}`, backgroundColor: COLORS.blueAlpha(0.1), color: COLORS.blue, fontFamily: 'inherit', backdropFilter: 'blur(4px)' }}>
            Scroll to bottom
          </button>
        )}
        <div ref={logAreaRef} style={{ ...S.logArea, position: 'absolute', inset: 0 }} onScroll={handleScroll}>
        {filteredLogs.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: COLORS.textDimmer, fontSize: 12 }}>
            {connected ? 'En attente de messages WebSocket...' : 'WebSocket deconnecte'}
          </div>
        )}
        {filteredLogs.map(log => (
          <div key={log.id} style={S.logLine}>
            <span style={S.ts}>{log.ts}</span>
            <span style={{ ...S.channel, color: CHANNEL_COLORS[log.channel] || COLORS.textDim }}>{log.channel}</span>
            <span style={S.type}>{log.type}</span>
            <span style={S.preview}>{log.preview}</span>
          </div>
        ))}
        </div>
      </div>

      <div style={S.stats}>
        <span>Total: {logs.length} msgs</span>
        <span>Affiches: {filteredLogs.length}</span>
        <span>Buffer: {MAX_LOGS}</span>
        <span style={{ color: paused ? COLORS.red : COLORS.green }}>
          {paused ? 'PAUSE' : 'LIVE'}
        </span>
        <span style={{ color: autoScroll ? COLORS.green : COLORS.textDimmer }}>
          {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
        </span>
        <div style={{ flex: 1 }} />
        <span>{connected ? 'WS Connected' : 'WS Disconnected'}</span>
      </div>
    </div>
  );
}
