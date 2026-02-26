import React, { useState, useEffect } from 'react';

type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'lmstudio' | 'settings';

interface TopBarProps {
  connected: boolean;
  currentPage: Page;
  onDetach?: () => void;
}

const PAGE_LABELS: Record<Page, string> = {
  dashboard: 'COMMAND CENTER',
  chat: 'CHAT',
  trading: 'TRADING',
  voice: 'VOICE',
  lmstudio: 'LM STUDIO',
  settings: 'SETTINGS',
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

export default function TopBar({ connected, currentPage, onDetach }: TopBarProps) {
  const [hovered, setHovered] = useState('');

  const detachable = ['dashboard', 'trading', 'voice'].includes(currentPage);
  const api = (window as any).electronAPI;

  return (
    <>
      <style>{CSS}</style>
      <div style={s.bar}>
        <span style={s.brand}>JARVIS TURBO</span>
        <span style={s.page}>{PAGE_LABELS[currentPage]}</span>
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
