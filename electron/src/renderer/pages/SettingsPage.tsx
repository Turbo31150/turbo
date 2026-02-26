import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

const CSS = `
.s-toggle{position:relative;width:36px;height:20px;border-radius:10px;cursor:pointer;transition:all .2s;border:none}
.s-toggle::after{content:'';position:absolute;width:16px;height:16px;border-radius:50%;top:2px;left:2px;background:#fff;transition:transform .2s}
.s-toggle.on{background:#10b981}.s-toggle.on::after{transform:translateX(16px)}
.s-toggle.off{background:#2a3a4a}
.s-section:hover{border-color:rgba(249,115,22,.2)!important}
`;

interface Config {
  cluster: { nodes: { id: string; name: string; url: string; enabled: boolean; weight: number }[] };
  trading: { pairs: string[]; leverage: number; tp_pct: number; sl_pct: number; position_size: number; dry_run: boolean };
  voice: { wake_word: string; confidence: number; tts_engine: string; language: string };
  general: { theme: string; language: string; auto_start: boolean; notifications: boolean };
}

const DEFAULT_CONFIG: Config = {
  cluster: { nodes: [
    { id: 'M1', name: 'M1 / qwen3-30b', url: '10.5.0.2:1234', enabled: true, weight: 1.8 },
    { id: 'M2', name: 'M2 / deepseek', url: '192.168.1.26:1234', enabled: true, weight: 1.4 },
    { id: 'M3', name: 'M3 / mistral', url: '192.168.1.113:1234', enabled: true, weight: 1.0 },
    { id: 'OL1', name: 'OL1 / qwen3:1.7b', url: '127.0.0.1:11434', enabled: true, weight: 1.3 },
    { id: 'Gemini', name: 'Gemini API', url: 'gemini-proxy', enabled: true, weight: 1.2 },
  ]},
  trading: { pairs: ['BTCUSDT','ETHUSDT','SOLUSDT','SUIUSDT','PEPEUSDT'], leverage: 10, tp_pct: 0.4, sl_pct: 0.25, position_size: 10, dry_run: true },
  voice: { wake_word: 'jarvis', confidence: 0.7, tts_engine: 'edge', language: 'fr-FR' },
  general: { theme: 'dark', language: 'fr', auto_start: false, notifications: true },
};

const S = {
  page: { padding: 20, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflowY: 'auto' } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: '#e0e0e0', marginBottom: 20 } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16 } as React.CSSProperties,
  section: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: 20, transition: 'border-color .3s' } as React.CSSProperties,
  secTitle: { fontSize: 12, fontWeight: 700, color: '#f97316', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 } as React.CSSProperties,
  secIcon: { fontSize: 16 } as React.CSSProperties,
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #0a0e14' } as React.CSSProperties,
  label: { fontSize: 12, color: '#c0c0c0' } as React.CSSProperties,
  value: { fontSize: 12, color: '#e0e0e0', fontWeight: 600 } as React.CSSProperties,
  muted: { fontSize: 10, color: '#6b7280' } as React.CSSProperties,
  nodeRow: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid #0a0e14' } as React.CSSProperties,
  dot: { width: 8, height: 8, borderRadius: '50%', flexShrink: 0 } as React.CSSProperties,
  dotOn: { backgroundColor: '#10b981', boxShadow: '0 0 6px rgba(16,185,129,.5)' },
  dotOff: { backgroundColor: '#4b5563' },
  nodeName: { flex: 1, fontSize: 12, color: '#e0e0e0' } as React.CSSProperties,
  nodeUrl: { fontSize: 10, color: '#6b7280' } as React.CSSProperties,
  nodeWeight: { fontSize: 11, color: '#f97316', fontWeight: 700, minWidth: 30, textAlign: 'right' } as React.CSSProperties,
  tag: { display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, backgroundColor: '#1a2a3a', color: '#c0c0c0', marginRight: 4, marginBottom: 4 } as React.CSSProperties,
};

function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return <button className={`s-toggle ${on ? 'on' : 'off'}`} onClick={onChange} />;
}

export default function SettingsPage() {
  const [cfg, setCfg] = useState<Config>(DEFAULT_CONFIG);
  const { connected, request } = useWebSocket();

  useEffect(() => {
    if (!connected) return;
    request('config', 'get_config').then(r => {
      if (r.payload) setCfg(prev => ({ ...prev, ...r.payload }));
    }).catch(() => {});
  }, [connected, request]);

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={S.title}>Configuration</div>
        <div style={S.grid}>

          {/* Cluster */}
          <div className="s-section" style={S.section}>
            <div style={S.secTitle}><span style={S.secIcon}>{'\uD83D\uDDA5'}</span> Cluster Nodes</div>
            {cfg.cluster.nodes.map(n => (
              <div key={n.id} style={S.nodeRow}>
                <span style={{ ...S.dot, ...(n.enabled ? S.dotOn : S.dotOff) }} />
                <div style={{ flex: 1 }}>
                  <div style={S.nodeName}>{n.name}</div>
                  <div style={S.nodeUrl}>{n.url}</div>
                </div>
                <span style={S.nodeWeight}>{n.weight}x</span>
                <Toggle on={n.enabled} onChange={() => {
                  setCfg(p => ({
                    ...p, cluster: { ...p.cluster, nodes: p.cluster.nodes.map(nn => nn.id === n.id ? { ...nn, enabled: !nn.enabled } : nn) }
                  }));
                }} />
              </div>
            ))}
          </div>

          {/* Trading */}
          <div className="s-section" style={S.section}>
            <div style={S.secTitle}><span style={S.secIcon}>{'\uD83D\uDCC8'}</span> Trading</div>
            <div style={S.row}>
              <span style={S.label}>Leverage</span>
              <span style={{ ...S.value, color: '#f97316' }}>{cfg.trading.leverage}x</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Take Profit</span>
              <span style={{ ...S.value, color: '#10b981' }}>{cfg.trading.tp_pct}%</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Stop Loss</span>
              <span style={{ ...S.value, color: '#ef4444' }}>{cfg.trading.sl_pct}%</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Taille position</span>
              <span style={S.value}>{cfg.trading.position_size} USDT</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Mode Dry Run</span>
              <Toggle on={cfg.trading.dry_run} onChange={() => setCfg(p => ({ ...p, trading: { ...p.trading, dry_run: !p.trading.dry_run } }))} />
            </div>
            <div style={{ marginTop: 10 }}>
              <div style={S.muted}>PAIRES</div>
              <div style={{ marginTop: 6 }}>
                {cfg.trading.pairs.map(p => <span key={p} style={S.tag}>{p}</span>)}
              </div>
            </div>
          </div>

          {/* Voice */}
          <div className="s-section" style={S.section}>
            <div style={S.secTitle}><span style={S.secIcon}>{'\uD83C\uDF99'}</span> Voice</div>
            <div style={S.row}>
              <span style={S.label}>Wake Word</span>
              <span style={{ ...S.value, color: '#c084fc' }}>{cfg.voice.wake_word}</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Confidence</span>
              <span style={S.value}>{(cfg.voice.confidence * 100).toFixed(0)}%</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>TTS Engine</span>
              <span style={{ ...S.value, textTransform: 'capitalize' } as React.CSSProperties}>{cfg.voice.tts_engine}</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Langue</span>
              <span style={S.value}>{cfg.voice.language}</span>
            </div>
          </div>

          {/* General */}
          <div className="s-section" style={S.section}>
            <div style={S.secTitle}><span style={S.secIcon}>{'\u2699\uFE0F'}</span> General</div>
            <div style={S.row}>
              <span style={S.label}>Theme</span>
              <span style={{ ...S.value, textTransform: 'capitalize' } as React.CSSProperties}>{cfg.general.theme}</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Langue</span>
              <span style={S.value}>{cfg.general.language.toUpperCase()}</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Auto-start</span>
              <Toggle on={cfg.general.auto_start} onChange={() => setCfg(p => ({ ...p, general: { ...p.general, auto_start: !p.general.auto_start } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Notifications</span>
              <Toggle on={cfg.general.notifications} onChange={() => setCfg(p => ({ ...p, general: { ...p.general, notifications: !p.general.notifications } }))} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
