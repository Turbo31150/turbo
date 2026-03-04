import React, { useState, useEffect, useCallback, memo } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API_BASE = 'http://127.0.0.1:9742';

const CSS = `
@keyframes mtFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.mt-page::-webkit-scrollbar{width:5px}
.mt-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
.mt-card{animation:mtFade .2s ease;transition:border-color .3s}
.mt-card:hover{border-color:${COLORS.orangeAlpha(0.25)}!important}
.mt-btn{background:transparent;border:1px solid ${COLORS.border};color:${COLORS.text};padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px}
.mt-btn:hover{border-color:${COLORS.orange};color:${COLORS.orange}}
`;

interface Snapshot {
  ts: number;
  orchestrator?: { health_score: number; total_tokens: number; total_calls: number; active_nodes: number };
  load_balancer?: { active_requests: number; circuit_broken_nodes: number; total_nodes: number };
  autonomous_loop?: { running: boolean; task_count: number; total_runs: number; total_fails: number; event_count: number };
  agent_memory?: { total_memories: number; categories: number };
  conversations?: { total_conversations: number; total_turns: number; total_tokens: number; avg_latency_ms: number };
  proactive?: { last_suggestions: number; dismissed: number };
  optimizer?: { total_adjustments: number; enabled: boolean };
  event_bus?: { subscriptions: number; total_events: number };
}

const Card = memo(({ title, color = COLORS.border, children }: { title: string; color?: string; children: React.ReactNode }) => (
  <div className="mt-card" style={{
    background: COLORS.bgCard, border: `1px solid ${color}`,
    borderRadius: 6, padding: 12, flex: '1 1 200px', minWidth: 180,
  }}>
    <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>{title}</div>
    {children}
  </div>
));

const Stat = memo(({ label, value, unit = '', color = COLORS.text }: { label: string; value: string | number; unit?: string; color?: string }) => (
  <div style={{ marginBottom: 4 }}>
    <span style={{ fontSize: 10, color: COLORS.textDim }}>{label}: </span>
    <span style={{ fontSize: 13, fontWeight: 600, color, fontFamily: FONT.mono }}>{value}</span>
    {unit && <span style={{ fontSize: 10, color: COLORS.textDim }}> {unit}</span>}
  </div>
));

const HealthBar = memo(({ score }: { score: number }) => {
  const color = score >= 80 ? COLORS.green : score >= 50 ? COLORS.orange : COLORS.red;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <div style={{ flex: 1, height: 6, background: COLORS.bgInput, borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(score, 100)}%`, height: '100%', background: color, borderRadius: 3, transition: 'width .5s' }} />
      </div>
      <span style={{ fontSize: 14, fontWeight: 700, color, fontFamily: FONT.mono }}>{score}</span>
    </div>
  );
});

const MiniChart = memo(({ data, color = COLORS.orange, height = 40 }: { data: number[]; color?: string; height?: number }) => {
  if (data.length < 2) return null;
  const max = Math.max(...data, 1);
  const w = 200;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${height - (v / max) * height}`).join(' ');
  return (
    <svg width={w} height={height} style={{ marginTop: 4 }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
});

export default function MetricsPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [snapRes, histRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/metrics/snapshot`),
        fetch(`${API_BASE}/api/metrics/history?minutes=30`),
      ]);
      if (snapRes.status === 'fulfilled') setSnapshot(await snapRes.value.json());
      if (histRes.status === 'fulfilled') {
        const d = await histRes.value.json();
        setHistory(d.history || []);
      }
    } catch {}
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchData, 5000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchData]);

  const healthScores = history.map(h => h.orchestrator?.health_score || 0);
  const tokenHistory = history.map(h => h.orchestrator?.total_tokens || 0);
  const latencyHistory = history.map(h => h.conversations?.avg_latency_ms || 0);

  const o = snapshot?.orchestrator;
  const lb = snapshot?.load_balancer;
  const al = snapshot?.autonomous_loop;
  const mem = snapshot?.agent_memory;
  const conv = snapshot?.conversations;
  const pa = snapshot?.proactive;
  const opt = snapshot?.optimizer;
  const eb = snapshot?.event_bus;

  return (
    <div className="mt-page" style={{
      height: '100%', overflow: 'auto', padding: 20,
      background: COLORS.bg, color: COLORS.text, fontFamily: FONT.sans,
    }}>
      <style>{CSS}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 20 }}>METRICS</span>
        <span style={{ fontSize: 12, color: COLORS.textDim }}>Real-time System Monitoring</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="mt-btn" onClick={() => setAutoRefresh(!autoRefresh)}>
            {autoRefresh ? 'Pause' : 'Resume'}
          </button>
          <button className="mt-btn" onClick={fetchData}>Refresh</button>
        </div>
      </div>

      {!snapshot ? (
        <div style={{ textAlign: 'center', color: COLORS.textDim, padding: 40 }}>Chargement...</div>
      ) : (
        <>
          {/* Row 1: Health + Orchestrator + LB */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <Card title="Cluster Health" color={COLORS.green}>
              <HealthBar score={o?.health_score || 0} />
              <MiniChart data={healthScores} color={COLORS.green} />
            </Card>
            <Card title="Orchestrator">
              <Stat label="Calls" value={o?.total_calls || 0} />
              <Stat label="Tokens" value={(o?.total_tokens || 0).toLocaleString()} />
              <Stat label="Active Nodes" value={o?.active_nodes || 0} color={COLORS.green} />
            </Card>
            <Card title="Load Balancer" color={lb?.circuit_broken_nodes ? COLORS.red : COLORS.border}>
              <Stat label="Active Reqs" value={lb?.active_requests || 0} color={COLORS.orange} />
              <Stat label="Nodes" value={lb?.total_nodes || 0} />
              <Stat label="Circuit Broken" value={lb?.circuit_broken_nodes || 0} color={lb?.circuit_broken_nodes ? COLORS.red : COLORS.green} />
            </Card>
          </div>

          {/* Row 2: Autonomous + Memory + Conversations */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <Card title="Autonomous Loop" color={al?.running ? COLORS.green : COLORS.red}>
              <Stat label="Status" value={al?.running ? 'RUNNING' : 'STOPPED'} color={al?.running ? COLORS.green : COLORS.red} />
              <Stat label="Tasks" value={al?.task_count || 0} />
              <Stat label="Runs" value={al?.total_runs || 0} />
              <Stat label="Fails" value={al?.total_fails || 0} color={al?.total_fails ? COLORS.red : COLORS.green} />
            </Card>
            <Card title="Agent Memory" color={COLORS.purple}>
              <Stat label="Memories" value={mem?.total_memories || 0} color={COLORS.purple} />
              <Stat label="Categories" value={mem?.categories || 0} />
            </Card>
            <Card title="Conversations">
              <Stat label="Conversations" value={conv?.total_conversations || 0} />
              <Stat label="Turns" value={conv?.total_turns || 0} />
              <Stat label="Tokens" value={(conv?.total_tokens || 0).toLocaleString()} />
              <Stat label="Avg Latency" value={conv?.avg_latency_ms?.toFixed(0) || '0'} unit="ms" />
            </Card>
          </div>

          {/* Row 3: Proactive + Optimizer + Event Bus */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <Card title="Proactive Agent">
              <Stat label="Suggestions" value={pa?.last_suggestions || 0} />
              <Stat label="Dismissed" value={pa?.dismissed || 0} />
            </Card>
            <Card title="Auto-Optimizer" color={opt?.enabled ? COLORS.green : COLORS.border}>
              <Stat label="Status" value={opt?.enabled ? 'ENABLED' : 'DISABLED'} color={opt?.enabled ? COLORS.green : COLORS.textDim} />
              <Stat label="Adjustments" value={opt?.total_adjustments || 0} />
            </Card>
            <Card title="Event Bus">
              <Stat label="Subscriptions" value={eb?.subscriptions || 0} />
              <Stat label="Events Emitted" value={eb?.total_events || 0} />
            </Card>
          </div>

          {/* Row 4: Charts */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Card title="Token Usage (30min)">
              <MiniChart data={tokenHistory} color={COLORS.orange} height={50} />
            </Card>
            <Card title="Avg Latency (30min)">
              <MiniChart data={latencyHistory} color={COLORS.purple} height={50} />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
