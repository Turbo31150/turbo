import React, { useState, useEffect, useCallback, memo } from 'react';
import { COLORS, FONT, FONTS } from '../lib/theme';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

interface NodeStat {
  total_calls: number;
  success_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  last_call: number;
  last_failure: number;
}

interface BudgetReport {
  total_tokens: number;
  total_calls: number;
  tokens_by_node: Record<string, number>;
  calls_by_node: Record<string, number>;
  session_duration_s: number;
  tokens_per_minute: number;
}

interface RoutingEntry {
  node: string;
  weight: number;
}

interface AutonomousTask {
  enabled: boolean;
  interval_s: number;
  run_count: number;
  fail_count: number;
  last_run: number;
  last_result: Record<string, unknown>;
}

interface AutonomousStatus {
  running: boolean;
  tick_interval_s: number;
  tasks: Record<string, AutonomousTask>;
  event_count: number;
  recent_events: Array<{ ts: number; task: string; level: string; message: string }>;
}

// ═══════════════════════════════════════════════════════════════
// CSS
// ═══════════════════════════════════════════════════════════════

const CSS = `
@keyframes oPulse{0%,100%{opacity:1}50%{opacity:.4}}
@keyframes oFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.o-page::-webkit-scrollbar{width:5px}
.o-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
.o-card{animation:oFade .2s ease;transition:border-color .3s,transform .15s}
.o-card:hover{border-color:${COLORS.orangeAlpha(0.25)}!important;transform:translateY(-1px)}
.o-bar{transition:width .4s ease}
`;

const API_BASE = 'http://127.0.0.1:9742';

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function scoreColor(score: number): string {
  if (score >= 80) return COLORS.green;
  if (score >= 50) return COLORS.yellow;
  return COLORS.red;
}

function latencyColor(ms: number): string {
  if (ms <= 200) return COLORS.green;
  if (ms <= 1000) return COLORS.yellow;
  return COLORS.red;
}

function fmtTs(ts: number): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString('fr-FR');
}

// ═══════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════

const Card = memo(({ title, children, color = COLORS.border }: {
  title: string; children: React.ReactNode; color?: string;
}) => (
  <div className="o-card" style={{
    background: COLORS.bgCard, border: `1px solid ${color}`,
    borderRadius: 8, padding: 16, marginBottom: 12,
  }}>
    <div style={{ color: COLORS.textMuted, fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
      {title}
    </div>
    {children}
  </div>
));

const StatBox = memo(({ label, value, color = COLORS.text }: {
  label: string; value: string | number; color?: string;
}) => (
  <div style={{ textAlign: 'center', flex: 1, minWidth: 80 }}>
    <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: FONTS.mono }}>{value}</div>
    <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 2 }}>{label}</div>
  </div>
));

const BarChart = memo(({ data, maxVal }: { data: Array<{ label: string; value: number; color: string }>; maxVal?: number }) => {
  const max = maxVal || Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {data.map(d => (
        <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 50, fontSize: 10, color: COLORS.textDim, textAlign: 'right', fontFamily: FONTS.mono }}>{d.label}</div>
          <div style={{ flex: 1, height: 14, background: COLORS.border, borderRadius: 4, overflow: 'hidden' }}>
            <div className="o-bar" style={{ width: `${(d.value / max) * 100}%`, height: '100%', background: d.color, borderRadius: 4 }} />
          </div>
          <div style={{ width: 50, fontSize: 10, color: COLORS.text, fontFamily: FONTS.mono }}>{d.value.toFixed(0)}</div>
        </div>
      ))}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════

export default function OrchestratorPage() {
  const [healthScore, setHealthScore] = useState(0);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [nodeStats, setNodeStats] = useState<Record<string, NodeStat>>({});
  const [budget, setBudget] = useState<BudgetReport | null>(null);
  const [routing, setRouting] = useState<Record<string, RoutingEntry[]>>({});
  const [autonomous, setAutonomous] = useState<AutonomousStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [healthRes, nodesRes, budgetRes, routingRes, autoRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/orchestrator/health`).then(r => r.json()),
        fetch(`${API_BASE}/api/orchestrator/nodes`).then(r => r.json()),
        fetch(`${API_BASE}/api/orchestrator/budget`).then(r => r.json()),
        fetch(`${API_BASE}/api/orchestrator/routing`).then(r => r.json()),
        fetch(`${API_BASE}/api/autonomous/status`).then(r => r.json()),
      ]);

      if (healthRes.status === 'fulfilled') {
        setHealthScore(healthRes.value.health_score ?? 0);
        setAlerts(healthRes.value.alerts ?? []);
      }
      if (nodesRes.status === 'fulfilled') setNodeStats(nodesRes.value);
      if (budgetRes.status === 'fulfilled') setBudget(budgetRes.value);
      if (routingRes.status === 'fulfilled') setRouting(routingRes.value);
      if (autoRes.status === 'fulfilled') setAutonomous(autoRes.value);
    } catch (e) {
      console.error('Orchestrator fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 10000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const nodeEntries = Object.entries(nodeStats);
  const latencyData = nodeEntries.map(([name, s]) => ({
    label: name, value: s.avg_latency_ms, color: latencyColor(s.avg_latency_ms),
  }));
  const callsData = nodeEntries.map(([name, s]) => ({
    label: name, value: s.total_calls, color: COLORS.blue,
  }));

  return (
    <div className="o-page" style={{
      height: '100%', overflow: 'auto', padding: 20,
      background: COLORS.bg, color: COLORS.text, fontFamily: FONTS.sans,
    }}>
      <style>{CSS}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <span style={{ fontSize: 20 }}>ORCHESTRATOR</span>
        <span style={{ fontSize: 12, color: COLORS.textDim }}>v2 — Phase 4</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={fetchAll} style={{
            background: 'transparent', border: `1px solid ${COLORS.border}`,
            color: COLORS.text, padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
          }}>Refresh</button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: COLORS.textDim, padding: 40 }}>Chargement...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 12 }}>

          {/* Health Score */}
          <Card title="Sante Cluster" color={scoreColor(healthScore)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <StatBox label="Score" value={healthScore} color={scoreColor(healthScore)} />
              <StatBox label="Alertes" value={alerts.length} color={alerts.length > 0 ? COLORS.red : COLORS.green} />
              <StatBox label="Noeuds" value={nodeEntries.length} color={COLORS.blue} />
            </div>
            {alerts.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 11, color: COLORS.red }}>
                {alerts.slice(0, 3).map((a, i) => (
                  <div key={i}>⚠ {a.message || JSON.stringify(a)}</div>
                ))}
              </div>
            )}
          </Card>

          {/* Budget */}
          {budget && (
            <Card title="Budget Tokens">
              <div style={{ display: 'flex', gap: 8 }}>
                <StatBox label="Total Tokens" value={budget.total_tokens.toLocaleString()} color={COLORS.orange} />
                <StatBox label="Appels" value={budget.total_calls} color={COLORS.blue} />
                <StatBox label="tok/min" value={budget.tokens_per_minute.toFixed(0)} color={COLORS.cyan} />
              </div>
              <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 8 }}>
                Session: {(budget.session_duration_s / 60).toFixed(1)} min
              </div>
            </Card>
          )}

          {/* Latency Chart */}
          {latencyData.length > 0 && (
            <Card title="Latence par Noeud (ms)">
              <BarChart data={latencyData} />
            </Card>
          )}

          {/* Calls Chart */}
          {callsData.length > 0 && (
            <Card title="Appels par Noeud">
              <BarChart data={callsData} />
            </Card>
          )}

          {/* Node Stats Table */}
          <Card title="Statistiques Noeuds">
            <div style={{ fontSize: 11, fontFamily: FONTS.mono }}>
              <div style={{ display: 'grid', gridTemplateColumns: '60px 50px 60px 70px 60px', gap: 4, color: COLORS.textDim, marginBottom: 4, fontWeight: 600 }}>
                <span>Noeud</span><span>Calls</span><span>Succes</span><span>Latence</span><span>Tokens</span>
              </div>
              {nodeEntries.map(([name, s]) => (
                <div key={name} style={{ display: 'grid', gridTemplateColumns: '60px 50px 60px 70px 60px', gap: 4, padding: '2px 0' }}>
                  <span style={{ color: COLORS.orange }}>{name}</span>
                  <span>{s.total_calls}</span>
                  <span style={{ color: s.success_rate >= 0.9 ? COLORS.green : COLORS.red }}>
                    {(s.success_rate * 100).toFixed(0)}%
                  </span>
                  <span style={{ color: latencyColor(s.avg_latency_ms) }}>
                    {s.avg_latency_ms.toFixed(0)}ms
                  </span>
                  <span>{s.total_tokens}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Routing Matrix */}
          <Card title="Matrice de Routage">
            <div style={{ fontSize: 11, fontFamily: FONTS.mono, maxHeight: 200, overflow: 'auto' }}>
              {Object.entries(routing).map(([taskType, entries]) => (
                <div key={taskType} style={{ marginBottom: 6 }}>
                  <span style={{ color: COLORS.purple, fontWeight: 600 }}>{taskType}:</span>{' '}
                  {entries.map((e, i) => (
                    <span key={i}>
                      <span style={{ color: COLORS.orange }}>{e.node}</span>
                      <span style={{ color: COLORS.textDim }}>({e.weight})</span>
                      {i < entries.length - 1 ? ' → ' : ''}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          </Card>

          {/* Autonomous Loop */}
          {autonomous && (
            <Card title="Boucle Autonome" color={autonomous.running ? COLORS.green : COLORS.red}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <StatBox label="Status" value={autonomous.running ? 'ACTIVE' : 'STOP'} color={autonomous.running ? COLORS.green : COLORS.red} />
                <StatBox label="Events" value={autonomous.event_count} color={COLORS.blue} />
                <StatBox label="Tick" value={`${autonomous.tick_interval_s}s`} color={COLORS.textMuted} />
              </div>
              <div style={{ fontSize: 11, fontFamily: FONTS.mono }}>
                {Object.entries(autonomous.tasks).map(([name, t]) => (
                  <div key={name} style={{ display: 'flex', gap: 8, padding: '2px 0', borderBottom: `1px solid ${COLORS.border}` }}>
                    <span style={{ width: 100, color: t.enabled ? COLORS.green : COLORS.textDim }}>{name}</span>
                    <span style={{ width: 40 }}>{t.run_count}x</span>
                    <span style={{ width: 40, color: t.fail_count > 0 ? COLORS.red : COLORS.textDim }}>{t.fail_count}F</span>
                    <span style={{ color: COLORS.textDim }}>{t.interval_s}s</span>
                  </div>
                ))}
              </div>
              {autonomous.recent_events.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 10, color: COLORS.textDim, maxHeight: 80, overflow: 'auto' }}>
                  {autonomous.recent_events.slice(-5).reverse().map((ev, i) => (
                    <div key={i} style={{ color: ev.level === 'alert' ? COLORS.red : ev.level === 'error' ? COLORS.yellow : COLORS.textDim }}>
                      {fmtTs(ev.ts)} [{ev.task}] {ev.message}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
