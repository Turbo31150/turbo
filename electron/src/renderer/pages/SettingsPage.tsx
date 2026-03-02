import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { APP_VERSION, APP_NAME, APP_STACK, BACKEND_URL } from '../lib/config';

const CSS = `
.s-toggle{position:relative;width:36px;height:20px;border-radius:10px;cursor:pointer;transition:all .2s;border:none}
.s-toggle::after{content:'';position:absolute;width:16px;height:16px;border-radius:50%;top:2px;left:2px;background:#fff;transition:transform .2s}
.s-toggle.on{background:#10b981}.s-toggle.on::after{transform:translateX(16px)}
.s-toggle.off{background:#2a3a4a}
.s-section:hover{border-color:rgba(249,115,22,.2)!important}
.s-save{transition:all .2s;cursor:pointer}.s-save:hover{background:#f97316!important;color:#0a0e14!important;transform:translateY(-1px);box-shadow:0 4px 12px rgba(249,115,22,.3)}
.s-save:active{transform:translateY(0)}
@keyframes s-toast-in{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}
`;

interface Config {
  cluster: { nodes: { id: string; name: string; url: string; enabled: boolean; weight: number }[] };
  trading: { pairs: string[]; leverage: number; tp_pct: number; sl_pct: number; position_size: number; dry_run: boolean };
  voice: { wake_word: string; confidence: number; tts_engine: string; language: string };
  general: { theme: string; language: string; auto_start: boolean; notifications: boolean };
}

const DEFAULT_CONFIG: Config = {
  cluster: { nodes: [
    { id: 'M1', name: 'M1 / qwen3-8b', url: 'http://10.5.0.2:1234', enabled: true, weight: 1.8 },
    { id: 'M2', name: 'M2 / deepseek', url: 'http://192.168.1.26:1234', enabled: true, weight: 1.4 },
    { id: 'M3', name: 'M3 / mistral', url: 'http://192.168.1.113:1234', enabled: true, weight: 1.0 },
    { id: 'OL1', name: 'OL1 / qwen3:1.7b', url: 'http://127.0.0.1:11434', enabled: true, weight: 1.3 },
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

interface SystemAbout {
  os: string; os_version: string; hostname: string; python: string;
  cpu_count: number; memory: { total_gb: number }; disks: Record<string, { total_gb: number; free_gb: number }>;
}

export default function SettingsPage() {
  const [cfg, setCfg] = useState<Config>(DEFAULT_CONFIG);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [dirty, setDirty] = useState(false);
  const [about, setAbout] = useState<SystemAbout | null>(null);
  const { connected, request } = useWebSocket();
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    if (!connected) return;
    request('system', 'get_config').then(r => {
      if (mountedRef.current && r.payload?.config) setCfg(prev => ({ ...prev, ...r.payload.config }));
    }).catch(() => {});
    request('system', 'system_info').then(r => {
      if (mountedRef.current && r.payload) setAbout(r.payload as SystemAbout);
    }).catch(() => {});
    return () => { mountedRef.current = false; };
  }, [connected, request]);

  const updateCfg = (updater: (prev: Config) => Config) => {
    setCfg(prev => updater(prev));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await request('system', 'save_config', { config: cfg });
      if (res.payload?.saved) {
        setToast({ msg: 'Configuration sauvegardee', ok: true });
        setDirty(false);
      } else {
        setToast({ msg: res.payload?.error || 'Erreur sauvegarde', ok: false });
      }
    } catch {
      setToast({ msg: 'Erreur connexion', ok: false });
    }
    setSaving(false);
    setTimeout(() => setToast(null), 3000);
  };

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
          <div style={S.title}>Configuration</div>
          <div style={{ flex: 1 }} />
          {dirty && <span style={{ fontSize: 10, color: '#f97316', fontFamily: 'Consolas, monospace' }}>Modifications non sauvegardees</span>}
          <button className="s-save" onClick={handleSave} disabled={saving || !connected} style={{
            padding: '8px 24px', borderRadius: 8, fontSize: 12, fontWeight: 700,
            fontFamily: 'Consolas, monospace', letterSpacing: 1,
            backgroundColor: dirty ? '#f97316' : 'rgba(249,115,22,.15)',
            color: dirty ? '#0a0e14' : '#f97316',
            border: '1px solid rgba(249,115,22,.3)',
            opacity: saving ? 0.6 : 1,
          }}>
            {saving ? 'SAVING...' : 'SAVE'}
          </button>
        </div>
        {toast && (
          <div style={{
            padding: '8px 16px', borderRadius: 8, fontSize: 12, marginBottom: 12,
            fontFamily: 'Consolas, monospace', animation: 's-toast-in .3s ease',
            backgroundColor: toast.ok ? 'rgba(16,185,129,.1)' : 'rgba(239,68,68,.1)',
            border: `1px solid ${toast.ok ? 'rgba(16,185,129,.3)' : 'rgba(239,68,68,.3)'}`,
            color: toast.ok ? '#10b981' : '#ef4444',
          }}>{toast.msg}</div>
        )}
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
                  updateCfg(p => ({
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
              <input type="number" min={1} max={125} style={{ ...S.value, color: '#f97316', width: 60, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', textAlign: 'right', outline: 'none' }}
                value={cfg.trading.leverage}
                onChange={e => updateCfg(p => ({ ...p, trading: { ...p.trading, leverage: parseInt(e.target.value) || 1 } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Take Profit (%)</span>
              <input type="number" step="0.05" min={0.01} style={{ ...S.value, color: '#10b981', width: 70, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', textAlign: 'right', outline: 'none' }}
                value={cfg.trading.tp_pct}
                onChange={e => updateCfg(p => ({ ...p, trading: { ...p.trading, tp_pct: parseFloat(e.target.value) || 0.1 } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Stop Loss (%)</span>
              <input type="number" step="0.05" min={0.01} style={{ ...S.value, color: '#ef4444', width: 70, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', textAlign: 'right', outline: 'none' }}
                value={cfg.trading.sl_pct}
                onChange={e => updateCfg(p => ({ ...p, trading: { ...p.trading, sl_pct: parseFloat(e.target.value) || 0.1 } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Taille position (USDT)</span>
              <input type="number" min={1} style={{ ...S.value, width: 70, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', textAlign: 'right', outline: 'none', color: '#e0e0e0' }}
                value={cfg.trading.position_size}
                onChange={e => updateCfg(p => ({ ...p, trading: { ...p.trading, position_size: parseInt(e.target.value) || 10 } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Mode Dry Run</span>
              <Toggle on={cfg.trading.dry_run} onChange={() => updateCfg(p => ({ ...p, trading: { ...p.trading, dry_run: !p.trading.dry_run } }))} />
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
              <input type="text" style={{ ...S.value, color: '#c084fc', width: 100, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', outline: 'none' }}
                value={cfg.voice.wake_word}
                onChange={e => updateCfg(p => ({ ...p, voice: { ...p.voice, wake_word: e.target.value } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Confidence</span>
              <input type="number" step="0.05" min={0.1} max={1} style={{ ...S.value, width: 60, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', textAlign: 'right', outline: 'none', color: '#e0e0e0' }}
                value={cfg.voice.confidence}
                onChange={e => updateCfg(p => ({ ...p, voice: { ...p.voice, confidence: parseFloat(e.target.value) || 0.5 } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>TTS Engine</span>
              <select style={{ ...S.value, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', color: '#e0e0e0', cursor: 'pointer', outline: 'none' }}
                value={cfg.voice.tts_engine}
                onChange={e => updateCfg(p => ({ ...p, voice: { ...p.voice, tts_engine: e.target.value } }))}>
                <option value="edge">Edge TTS</option>
                <option value="piper">Piper</option>
                <option value="system">System</option>
              </select>
            </div>
            <div style={S.row}>
              <span style={S.label}>Langue</span>
              <select style={{ ...S.value, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', color: '#e0e0e0', cursor: 'pointer', outline: 'none' }}
                value={cfg.voice.language}
                onChange={e => updateCfg(p => ({ ...p, voice: { ...p.voice, language: e.target.value } }))}>
                <option value="fr-FR">Francais (fr-FR)</option>
                <option value="en-US">English (en-US)</option>
                <option value="en-GB">English (en-GB)</option>
              </select>
            </div>
          </div>

          {/* General */}
          <div className="s-section" style={S.section}>
            <div style={S.secTitle}><span style={S.secIcon}>{'\u2699\uFE0F'}</span> General</div>
            <div style={S.row}>
              <span style={S.label}>Theme</span>
              <select style={{ ...S.value, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', color: '#e0e0e0', cursor: 'pointer', outline: 'none' }}
                value={cfg.general.theme}
                onChange={e => updateCfg(p => ({ ...p, general: { ...p.general, theme: e.target.value } }))}>
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System</option>
              </select>
            </div>
            <div style={S.row}>
              <span style={S.label}>Langue</span>
              <select style={{ ...S.value, backgroundColor: '#0a0e14', border: '1px solid #2a3a4a', borderRadius: 4, padding: '2px 6px', fontFamily: 'inherit', color: '#e0e0e0', cursor: 'pointer', outline: 'none' }}
                value={cfg.general.language}
                onChange={e => updateCfg(p => ({ ...p, general: { ...p.general, language: e.target.value } }))}>
                <option value="fr">Francais</option>
                <option value="en">English</option>
              </select>
            </div>
            <div style={S.row}>
              <span style={S.label}>Auto-start</span>
              <Toggle on={cfg.general.auto_start} onChange={() => updateCfg(p => ({ ...p, general: { ...p.general, auto_start: !p.general.auto_start } }))} />
            </div>
            <div style={S.row}>
              <span style={S.label}>Notifications</span>
              <Toggle on={cfg.general.notifications} onChange={() => updateCfg(p => ({ ...p, general: { ...p.general, notifications: !p.general.notifications } }))} />
            </div>
          </div>

          {/* About */}
          <div className="s-section" style={S.section}>
            <div style={S.secTitle}><span style={S.secIcon}>{'\u2139\uFE0F'}</span> About</div>
            <div style={S.row}>
              <span style={S.label}>Application</span>
              <span style={{ ...S.value, color: '#f97316' }}>{APP_NAME} v{APP_VERSION}</span>
            </div>
            <div style={S.row}>
              <span style={S.label}>Stack</span>
              <span style={S.value}>{APP_STACK}</span>
            </div>
            {about && (
              <>
                <div style={S.row}>
                  <span style={S.label}>OS</span>
                  <span style={S.value}>{about.os} {about.os_version}</span>
                </div>
                <div style={S.row}>
                  <span style={S.label}>Hostname</span>
                  <span style={S.value}>{about.hostname}</span>
                </div>
                <div style={S.row}>
                  <span style={S.label}>Python</span>
                  <span style={S.value}>{about.python}</span>
                </div>
                <div style={S.row}>
                  <span style={S.label}>CPU Cores</span>
                  <span style={S.value}>{about.cpu_count}</span>
                </div>
                <div style={S.row}>
                  <span style={S.label}>RAM</span>
                  <span style={S.value}>{about.memory?.total_gb} GB</span>
                </div>
                {about.disks && Object.entries(about.disks).map(([d, info]) => (
                  <div key={d} style={S.row}>
                    <span style={S.label}>{d}</span>
                    <span style={S.value}>{(info as any).free_gb?.toFixed(0)} GB free / {(info as any).total_gb?.toFixed(0)} GB</span>
                  </div>
                ))}
              </>
            )}
            <div style={S.row}>
              <span style={S.label}>Backend</span>
              <span style={{ ...S.value, color: connected ? '#10b981' : '#ef4444' }}>{connected ? `${BACKEND_URL} OK` : 'Deconnecte'}</span>
            </div>
            <div style={{ marginTop: 10 }}>
              <div style={S.muted}>RACCOURCIS CLAVIER</div>
              <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {['Ctrl+1 Dashboard', 'Ctrl+2 Chat', 'Ctrl+3 AI Cluster', 'Ctrl+4 Voice', 'Ctrl+5 Dictionary', 'Ctrl+6 Pipelines', 'Ctrl+7 Toolbox', 'Ctrl+8 Trading', 'Ctrl+9 Logs', 'Ctrl+0 Settings'].map(k => (
                  <span key={k} style={S.tag}>{k}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
