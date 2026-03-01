import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useCluster, ClusterNode } from '../hooks/useCluster';
import { useLMStudio } from '../hooks/useLMStudio';
import { useWebSocket } from '../hooks/useWebSocket';
import { APP_VERSION } from '../lib/config';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface SystemInfo {
  os: string;
  cpu_percent: number;
  cpu_count: number;
  memory: { total_gb: number; used_gb: number; available_gb: number; percent: number };
  disks: Record<string, { total_gb: number; free_gb: number; used_gb: number; percent_used: number }>;
}

interface ActivityItem {
  id: number;
  type: 'cluster' | 'trading' | 'voice' | 'system' | 'chat';
  text: string;
  ts: number;
}

// ═══════════════════════════════════════════════════════════════
// CSS
// ═══════════════════════════════════════════════════════════════

const CSS = `
@keyframes dPulse{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes dFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes dGlow{0%,100%{box-shadow:0 0 4px rgba(16,185,129,.3)}50%{box-shadow:0 0 12px rgba(16,185,129,.6)}}
.d-page::-webkit-scrollbar{width:5px}
.d-page::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:3px}
.d-card{animation:dFade .2s ease;transition:border-color .3s,transform .15s}
.d-card:hover{border-color:rgba(249,115,22,.25)!important;transform:translateY(-1px)}
.d-action:hover{background:rgba(249,115,22,.12)!important;border-color:#f97316!important;color:#f97316!important}
.d-action:active{transform:scale(.96)}
.d-feed::-webkit-scrollbar{width:4px}
.d-feed::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:2px}
`;

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const STATUS_COLORS = {
  online: { bg: 'rgba(16,185,129,.12)', border: 'rgba(16,185,129,.3)', text: '#10b981', dot: '#10b981' },
  offline: { bg: 'rgba(239,68,68,.08)', border: 'rgba(239,68,68,.25)', text: '#ef4444', dot: '#ef4444' },
  degraded: { bg: 'rgba(249,115,22,.08)', border: 'rgba(249,115,22,.25)', text: '#f97316', dot: '#f97316' },
};

const QUICK_ACTIONS = [
  { id: 'health', label: 'Health Check', icon: '\u2764', channel: 'cluster', action: 'get_status' },
  { id: 'gpu', label: 'GPU Stats', icon: '\uD83C\uDFAE', channel: 'cluster', action: 'gpu_stats' },
  { id: 'system', label: 'Sys Info', icon: '\u2699', channel: 'system', action: 'system_info' },
  { id: 'scan', label: 'Scan Sniper', icon: '\uD83C\uDFAF', channel: 'chat', action: 'send_message' },
  { id: 'audit', label: 'Audit', icon: '\uD83D\uDD0D', channel: 'system', action: 'execute_command' },
];

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function ProgressBar({ value, max, color, height = 6 }: { value: number; max: number; color: string; height?: number }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div style={{ height, borderRadius: height / 2, backgroundColor: '#1a2a3a', overflow: 'hidden', width: '100%' }}>
      <div style={{ height: '100%', width: `${pct}%`, backgroundColor: color, borderRadius: height / 2, transition: 'width .5s ease' }} />
    </div>
  );
}

function StatCard({ label, value, suffix, color, sub }: { label: string; value: string | number; suffix?: string; color: string; sub?: string }) {
  return (
    <div className="d-card" style={{ backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: '16px 20px', flex: '1 1 180px', minWidth: 160 }}>
      <div style={{ fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5, fontWeight: 700, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>
        {value}{suffix && <span style={{ fontSize: 14, fontWeight: 500, color: '#6b7280', marginLeft: 2 }}>{suffix}</span>}
      </div>
      {sub && <div style={{ fontSize: 10, color: '#4b5563', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function NodeCard({ node, lmNode }: { node?: ClusterNode; lmNode?: any }) {
  const name = node?.name || lmNode?.id || '?';
  const status = node?.status || (lmNode?.status === 'online' ? 'online' : 'offline');
  const sc = STATUS_COLORS[status] || STATUS_COLORS.offline;
  const latency = node?.latency ?? lmNode?.latency ?? -1;
  const modelsLoaded = node?.models?.filter(m => m.loaded).length ?? lmNode?.models?.filter((m: any) => m.loaded).length ?? 0;
  const weight = node?.weight;
  const vramTotal = node?.vram_total || 0;
  const vramUsed = node?.vram_used || 0;
  const gpus = node?.gpus || [];
  const role = node?.role || lmNode?.role || '';
  const defaultModel = node?.default_model || lmNode?.default_model || '';
  const maxTemp = gpus.reduce((mx, g) => Math.max(mx, g.temperature || 0), 0);

  return (
    <div className="d-card" style={{ backgroundColor: '#0d1117', border: `1px solid ${sc.border}`, borderRadius: 10, padding: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: sc.dot, boxShadow: status === 'online' ? `0 0 8px ${sc.dot}` : 'none', flexShrink: 0 }} />
        <span style={{ fontSize: 14, fontWeight: 700, color: '#e0e0e0', flex: 1 }}>{name}</span>
        {weight != null && <span style={{ fontSize: 10, color: '#f97316', fontWeight: 700 }}>{weight}x</span>}
        <span style={{ fontSize: 10, color: sc.text, fontWeight: 600, padding: '2px 8px', borderRadius: 4, backgroundColor: sc.bg }}>{status.toUpperCase()}</span>
      </div>

      {/* Role + default model */}
      {(role || defaultModel) && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, fontSize: 10 }}>
          {role && <span style={{ color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>{role}</span>}
          {defaultModel && <span style={{ color: '#6b7280', fontWeight: 600 }}>{defaultModel}</span>}
        </div>
      )}

      {/* Metrics row */}
      <div style={{ display: 'flex', gap: 12, fontSize: 11, marginBottom: 8 }}>
        <div>
          <span style={{ color: '#6b7280' }}>Latence: </span>
          <span style={{ color: latency > 0 ? (latency < 500 ? '#10b981' : latency < 2000 ? '#f97316' : '#ef4444') : '#4b5563', fontWeight: 600 }}>
            {latency > 0 ? `${latency}ms` : '\u2014'}
          </span>
        </div>
        <div>
          <span style={{ color: '#6b7280' }}>Models: </span>
          <span style={{ color: modelsLoaded > 0 ? '#c084fc' : '#4b5563', fontWeight: 600 }}>{modelsLoaded}</span>
        </div>
        {gpus.length > 0 && (
          <div>
            <span style={{ color: '#6b7280' }}>GPU: </span>
            <span style={{ fontWeight: 600, color: '#e0e0e0' }}>{gpus.length}x</span>
          </div>
        )}
        {maxTemp > 0 && (
          <div>
            <span style={{ color: '#6b7280' }}>Temp: </span>
            <span style={{ fontWeight: 600, color: maxTemp > 80 ? '#ef4444' : maxTemp > 65 ? '#f97316' : '#10b981' }}>{maxTemp}C</span>
          </div>
        )}
      </div>

      {/* VRAM bar */}
      {vramTotal > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#6b7280', marginBottom: 3 }}>
            <span>VRAM</span>
            <span>{vramUsed > 0 ? `${(vramUsed / 1024).toFixed(1)}` : '?'} / {(vramTotal / 1024).toFixed(0)} GB</span>
          </div>
          <ProgressBar value={vramUsed || 0} max={vramTotal} color={vramUsed / vramTotal > 0.9 ? '#ef4444' : vramUsed / vramTotal > 0.7 ? '#f97316' : '#3b82f6'} height={5} />
        </div>
      )}

      {/* GPU details (compact) */}
      {gpus.length > 1 && gpus.some(g => g.temperature && g.temperature > 0) && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {gpus.map((g, i) => (
            <span key={i} style={{
              fontSize: 8, padding: '1px 5px', borderRadius: 3,
              backgroundColor: (g.temperature || 0) > 75 ? 'rgba(239,68,68,.1)' : 'rgba(59,130,246,.08)',
              color: (g.temperature || 0) > 75 ? '#ef4444' : '#6b7280',
              border: `1px solid ${(g.temperature || 0) > 75 ? 'rgba(239,68,68,.2)' : 'rgba(59,130,246,.15)'}`,
            }}>
              GPU{i} {g.temperature ? `${g.temperature}C` : ''}
            </span>
          ))}
        </div>
      )}

      {/* Model badges */}
      {node?.models && node.models.length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
          {node.models.filter(m => m.loaded).map(m => (
            <span key={m.id} style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: 'rgba(192,132,252,.1)', color: '#c084fc', border: '1px solid rgba(192,132,252,.2)' }}>
              {m.name || m.id}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════

export default function DashboardPage() {
  const { nodes: clusterNodes, loading: clusterLoading, refreshCluster } = useCluster();
  const { nodes: lmNodes, refreshing: lmRefreshing, refresh: refreshLM } = useLMStudio();
  const { connected, request, subscribe } = useWebSocket();

  const [sysInfo, setSysInfo] = useState<SystemInfo | null>(null);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [actionResult, setActionResult] = useState<string | null>(null);
  const actIdRef = useRef(0);

  // Fetch system info
  const fetchSysInfo = useCallback(async () => {
    if (!connected) return;
    try {
      const resp = await request('system', 'system_info');
      if (resp.payload) setSysInfo(resp.payload as SystemInfo);
    } catch { /* backend may not have system_info handler yet */ }
  }, [connected, request]);

  useEffect(() => {
    fetchSysInfo();
    const iv = setInterval(fetchSysInfo, 30000);
    return () => clearInterval(iv);
  }, [fetchSysInfo]);

  // Subscribe to events for activity feed
  useEffect(() => {
    const unsubs = ['cluster', 'trading', 'voice', 'chat', 'system'].map(ch =>
      subscribe(ch, (msg) => {
        if (msg.type === 'event' && msg.event) {
          setActivities(prev => {
            const item: ActivityItem = {
              id: ++actIdRef.current,
              type: ch as ActivityItem['type'],
              text: `[${ch}] ${msg.event}${msg.payload?.text ? ': ' + String(msg.payload.text).slice(0, 80) : ''}`,
              ts: Date.now(),
            };
            return [item, ...prev].slice(0, 50);
          });
        }
      })
    );
    return () => unsubs.forEach(u => u());
  }, [subscribe]);

  // Quick action handler
  const handleAction = useCallback(async (action: typeof QUICK_ACTIONS[0]) => {
    if (!connected) return;
    setActionResult(`Execution: ${action.label}...`);
    try {
      const payload = action.id === 'scan'
        ? { text: 'scan sniper 100 coins', agent: 'main' }
        : action.id === 'audit'
          ? { command: 'uv run python scripts/system_audit.py --quick', timeout: 30 }
          : {};
      const resp = await request(action.channel, action.action, payload);
      setActionResult(`${action.label} OK`);
      // Add to activity
      setActivities(prev => [{
        id: ++actIdRef.current,
        type: 'system' as const,
        text: `[action] ${action.label} execute avec succes`,
        ts: Date.now(),
      }, ...prev].slice(0, 50));
    } catch (e: any) {
      setActionResult(`${action.label}: ${e.message}`);
    }
    setTimeout(() => setActionResult(null), 4000);
  }, [connected, request]);

  const refreshAll = useCallback(() => {
    refreshCluster();
    refreshLM();
    fetchSysInfo();
  }, [refreshCluster, refreshLM, fetchSysInfo]);

  // Computed stats
  const onlineNodes = useMemo(() => {
    const clusterOnline = clusterNodes.filter(n => n.status === 'online').length;
    const lmOnline = lmNodes.filter(n => n.status === 'online').length;
    return Math.max(clusterOnline, lmOnline);
  }, [clusterNodes, lmNodes]);

  const totalModels = useMemo(() =>
    lmNodes.reduce((s, n) => s + n.models.filter(m => m.loaded).length, 0),
  [lmNodes]);

  const totalVRAM = useMemo(() =>
    Math.round(clusterNodes.reduce((s, n) => s + (n.vram_total || 0), 0) / 1024),
  [clusterNodes]);

  // Merge cluster + LM nodes for display
  const allNodes = useMemo(() => {
    const merged: { cluster?: ClusterNode; lm?: any; name: string }[] = [];
    const seen = new Set<string>();

    for (const cn of clusterNodes) {
      seen.add(cn.name);
      const lm = lmNodes.find(l => l.id === cn.name);
      merged.push({ cluster: cn, lm, name: cn.name });
    }
    for (const ln of lmNodes) {
      if (!seen.has(ln.id)) {
        merged.push({ lm: ln, name: ln.id });
      }
    }
    return merged;
  }, [clusterNodes, lmNodes]);

  const timeAgo = (ts: number) => {
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}min`;
    return `${Math.floor(s / 3600)}h`;
  };

  const CHAN_COLORS: Record<string, string> = {
    cluster: '#10b981', trading: '#f97316', voice: '#c084fc', system: '#6b7280', chat: '#3b82f6',
  };

  return (
    <>
      <style>{CSS}</style>
      <div className="d-page" style={{ padding: 20, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflowY: 'auto', backgroundColor: '#0a0e14' }}>

        {/* ═══ HEADER ═══ */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#e0e0e0', display: 'flex', alignItems: 'center', gap: 10 }}>
              JARVIS Command Center
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 12,
                backgroundColor: connected ? 'rgba(16,185,129,.12)' : 'rgba(239,68,68,.12)',
                color: connected ? '#10b981' : '#ef4444',
                border: `1px solid ${connected ? 'rgba(16,185,129,.3)' : 'rgba(239,68,68,.3)'}`,
              }}>
                {connected ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
            <div style={{ fontSize: 11, color: '#4b5563', marginTop: 2 }}>v{APP_VERSION} — Cluster distribue {allNodes.length} noeuds</div>
          </div>
          <button onClick={refreshAll}
            style={{ padding: '6px 16px', borderRadius: 6, border: '1px solid #2a3a4a', backgroundColor: 'transparent', color: '#6b7280', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s' }}>
            Actualiser
          </button>
        </div>

        {/* ═══ STAT CARDS ═══ */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
          <StatCard label="Noeuds en ligne" value={onlineNodes} suffix={`/${allNodes.length}`} color="#10b981" sub={clusterLoading ? 'Chargement...' : undefined} />
          <StatCard label="Modeles charges" value={totalModels} color="#c084fc" sub={lmRefreshing ? 'Rafraichissement...' : undefined} />
          <StatCard label="VRAM total" value={totalVRAM || '~78'} suffix="GB" color="#f97316" />
          <StatCard label="RAM" value={sysInfo ? `${sysInfo.memory.used_gb.toFixed(0)}` : '—'} suffix={sysInfo ? `/${sysInfo.memory.total_gb.toFixed(0)}GB` : ''} color="#3b82f6" sub={sysInfo ? `${sysInfo.memory.percent.toFixed(0)}% utilise` : 'En attente...'} />
          <StatCard label="CPU" value={sysInfo ? `${sysInfo.cpu_percent.toFixed(0)}` : '—'} suffix="%" color={sysInfo && sysInfo.cpu_percent > 80 ? '#ef4444' : '#10b981'} sub={sysInfo ? `${sysInfo.cpu_count} coeurs` : undefined} />
        </div>

        {/* ═══ DISKS ═══ */}
        {sysInfo?.disks && Object.keys(sysInfo.disks).length > 0 && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            {Object.entries(sysInfo.disks).map(([drive, info]) => {
              if ('error' in info) return null;
              const pct = info.percent_used ?? (info.used_gb / info.total_gb * 100);
              return (
                <div key={drive} className="d-card" style={{ backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 8, padding: '10px 16px', minWidth: 200, flex: '1 1 200px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#e0e0e0' }}>{drive}</span>
                    <span style={{ fontSize: 10, color: '#6b7280' }}>{info.free_gb.toFixed(0)} GB libre / {info.total_gb.toFixed(0)} GB</span>
                  </div>
                  <ProgressBar value={info.used_gb ?? (info.total_gb - info.free_gb)} max={info.total_gb} color={pct > 90 ? '#ef4444' : pct > 70 ? '#f97316' : '#10b981'} />
                </div>
              );
            })}
          </div>
        )}

        {/* ═══ CLUSTER NODES ═══ */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 10 }}>
            Cluster Nodes
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
            {allNodes.map(({ cluster, lm, name }) => (
              <NodeCard key={name} node={cluster} lmNode={lm} />
            ))}
            {allNodes.length === 0 && !clusterLoading && (
              <div style={{ padding: 30, textAlign: 'center', color: '#4b5563', fontSize: 12, gridColumn: '1/-1' }}>
                {connected ? 'Aucun noeud detecte' : 'Backend hors ligne — lance python_ws/server.py'}
              </div>
            )}
          </div>
        </div>

        {/* ═══ QUICK ACTIONS + ACTIVITY ═══ */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Quick Actions */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 10 }}>
              Actions rapides
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {QUICK_ACTIONS.map(a => (
                <button key={a.id} className="d-action"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                    backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 8,
                    color: '#c0c0c0', fontSize: 12, cursor: connected ? 'pointer' : 'not-allowed',
                    fontFamily: 'inherit', transition: 'all .2s', textAlign: 'left', width: '100%',
                    opacity: connected ? 1 : 0.4,
                  }}
                  onClick={() => handleAction(a)} disabled={!connected}>
                  <span style={{ fontSize: 16, width: 24, textAlign: 'center' }}>{a.icon}</span>
                  <span style={{ fontWeight: 600 }}>{a.label}</span>
                </button>
              ))}
              {actionResult && (
                <div style={{ fontSize: 11, color: actionResult.includes('OK') ? '#10b981' : '#f97316', padding: '4px 14px', animation: 'dFade .2s ease' }}>
                  {actionResult}
                </div>
              )}
            </div>
          </div>

          {/* Activity Feed */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 10 }}>
              Activite recente
            </div>
            <div className="d-feed" style={{ backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 10, padding: 12, maxHeight: 280, overflowY: 'auto' }}>
              {activities.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#4b5563', fontSize: 11, padding: 20 }}>
                  En attente d'evenements...
                </div>
              ) : (
                activities.map(a => (
                  <div key={a.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0', borderBottom: '1px solid #0a0e14', animation: 'dFade .3s ease' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: CHAN_COLORS[a.type] || '#6b7280', marginTop: 5, flexShrink: 0 }} />
                    <span style={{ flex: 1, fontSize: 11, color: '#c0c0c0', lineHeight: 1.4, wordBreak: 'break-word' }}>{a.text}</span>
                    <span style={{ fontSize: 9, color: '#4b5563', flexShrink: 0, marginTop: 2 }}>{timeAgo(a.ts)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
