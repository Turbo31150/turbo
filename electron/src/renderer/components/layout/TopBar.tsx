import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useCluster } from '../../hooks/useCluster';

type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'lmstudio' | 'settings' | 'dictionary' | 'pipelines' | 'toolbox' | 'logs';

interface TopBarProps {
  connected: boolean;
  currentPage: Page;
  onDetach?: () => void;
}

interface SystemMetrics {
  cpu_percent: number;
  memory: { percent: number; used_gb: number; total_gb: number };
}

const PAGE_LABELS: Record<Page, string> = {
  dashboard: 'COMMAND CENTER',
  chat: 'CHAT',
  trading: 'TRADING',
  voice: 'VOICE',
  lmstudio: 'AI CLUSTER',
  settings: 'SETTINGS',
  dictionary: 'DICTIONARY',
  pipelines: 'PIPELINES',
  toolbox: 'TOOLBOX',
  logs: 'LOGS',
};

const CSS = `
@keyframes topScan{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes statusPulse{0%,100%{opacity:1}50%{opacity:.5}}
`;

const s = {
  bar: {
    display: 'flex', alignItems: 'center', height: 40,
    backgroundColor: '#0d1117', borderBottom: '1px solid #1a2a3a',
    paddingLeft: 16, paddingRight: 8, gap: 12, flexShrink: 0,
    background: 'linear-gradient(90deg, #0d1117, rgba(249,115,22,.02), #0d1117)',
    backgroundSize: '200% 100%', animation: 'topScan 12s linear infinite',
    WebkitAppRegion: 'drag',
  } as React.CSSProperties,
  brand: {
    fontSize: 13, fontWeight: 700, letterSpacing: 3,
    background: 'linear-gradient(135deg, #f97316, #c084fc)',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
    fontFamily: 'Consolas, "Courier New", monospace',
  } as React.CSSProperties,
  page: {
    fontSize: 10, letterSpacing: 2, color: '#6b7280', fontWeight: 600,
    textTransform: 'uppercase', fontFamily: 'Consolas, monospace',
  } as React.CSSProperties,
  spacer: { flex: 1 } as React.CSSProperties,
  badge: {
    display: 'inline-flex', alignItems: 'center', gap: 5,
    padding: '2px 10px', borderRadius: 10, fontSize: 10,
    fontWeight: 700, letterSpacing: 1, fontFamily: 'Consolas, monospace',
  } as React.CSSProperties,
  badgeOn: { backgroundColor: 'rgba(16,185,129,.1)', border: '1px solid rgba(16,185,129,.25)', color: '#10b981' },
  badgeOff: { backgroundColor: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.25)', color: '#ef4444' },
  dot: { width: 6, height: 6, borderRadius: '50%' } as React.CSSProperties,
  dotOn: { backgroundColor: '#10b981', animation: 'statusPulse 2s ease infinite' },
  dotOff: { backgroundColor: '#ef4444' },
  btn: {
    background: 'none', border: '1px solid transparent', borderRadius: 4,
    color: '#6b7280', cursor: 'pointer', fontSize: 13, padding: '4px 8px',
    fontFamily: 'Consolas, monospace', transition: 'all .15s',
    WebkitAppRegion: 'no-drag',
  } as React.CSSProperties,
  winBtn: {
    background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer',
    fontSize: 14, padding: '4px 10px', transition: 'color .15s',
    WebkitAppRegion: 'no-drag',
  } as React.CSSProperties,
};

function MetricChip({ label, value, unit, color }: { label: string; value: string; unit?: string; color: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 6, fontSize: 9, fontWeight: 600,
      backgroundColor: `${color}11`, border: `1px solid ${color}33`,
      color, fontFamily: 'Consolas, monospace', letterSpacing: 0.5,
    } as React.CSSProperties}>
      <span style={{ opacity: 0.7 }}>{label}</span>
      <span>{value}{unit}</span>
    </span>
  );
}

export default function TopBar({ connected, currentPage, onDetach }: TopBarProps) {
  const [hovered, setHovered] = useState('');
  const [clock, setClock] = useState('');
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const { request } = useWebSocket();
  const { nodes } = useCluster();
  const intervalRef = useRef<number>(0);

  const onlineCount = nodes.filter(n => n.status === 'online').length;

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setClock(now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }));
    };
    updateClock();
    const t = window.setInterval(updateClock, 30000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!connected) return;
    const fetchMetrics = () => {
      request('system', 'system_info').then(r => {
        if (r.payload) setMetrics(r.payload as SystemMetrics);
      }).catch(() => {});
    };
    fetchMetrics();
    intervalRef.current = window.setInterval(fetchMetrics, 15000);
    return () => clearInterval(intervalRef.current);
  }, [connected, request]);

  const detachable = ['dashboard', 'trading', 'voice'].includes(currentPage);
  const api = (window as any).electronAPI;

  return (
    <>
      <style>{CSS}</style>
      <div style={s.bar}>
        <span style={s.brand}>JARVIS TURBO</span>
        <span style={s.page}>{PAGE_LABELS[currentPage]}</span>

        {/* Live metrics */}
        <div style={{ display: 'flex', gap: 6, marginLeft: 16, WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
          {metrics && (
            <>
              <MetricChip label="CPU" value={`${Math.round(metrics.cpu_percent)}`} unit="%" color={metrics.cpu_percent > 80 ? '#ef4444' : metrics.cpu_percent > 50 ? '#f97316' : '#10b981'} />
              <MetricChip label="RAM" value={`${Math.round(metrics.memory?.percent || 0)}`} unit="%" color={(metrics.memory?.percent || 0) > 85 ? '#ef4444' : '#3b82f6'} />
            </>
          )}
          <MetricChip label="NODES" value={`${onlineCount}/${nodes.length || '?'}`} unit="" color={onlineCount > 0 ? '#10b981' : '#ef4444'} />
          {clock && (
            <span style={{
              fontSize: 10, color: '#4b5563', fontFamily: 'Consolas, monospace',
              fontWeight: 600, letterSpacing: 1, padding: '2px 6px',
            } as React.CSSProperties}>{clock}</span>
          )}
        </div>

        <div style={s.spacer} />

        {detachable && onDetach && (
          <button
            style={{ ...s.btn, ...(hovered === 'detach' ? { borderColor: '#f97316', color: '#f97316' } : {}) }}
            onClick={onDetach}
            onMouseEnter={() => setHovered('detach')}
            onMouseLeave={() => setHovered('')}
            title="Detacher en widget"
          >
            Detach
          </button>
        )}

        <span style={{ ...s.badge, ...(connected ? s.badgeOn : s.badgeOff) }}>
          <span style={{ ...s.dot, ...(connected ? s.dotOn : s.dotOff) }} />
          {connected ? 'ONLINE' : 'OFFLINE'}
        </span>

        {/* Window controls */}
        <button style={{ ...s.winBtn, ...(hovered === 'min' ? { color: '#f97316' } : {}) }}
          onClick={() => api?.minimize?.()} onMouseEnter={() => setHovered('min')} onMouseLeave={() => setHovered('')}>
          &mdash;
        </button>
        <button style={{ ...s.winBtn, ...(hovered === 'max' ? { color: '#f97316' } : {}) }}
          onClick={() => api?.maximize?.()} onMouseEnter={() => setHovered('max')} onMouseLeave={() => setHovered('')}>
          &#9633;
        </button>
        <button style={{ ...s.winBtn, ...(hovered === 'close' ? { color: '#ef4444' } : {}) }}
          onClick={() => api?.close?.()} onMouseEnter={() => setHovered('close')} onMouseLeave={() => setHovered('')}>
          &#10005;
        </button>
      </div>
    </>
  );
}
