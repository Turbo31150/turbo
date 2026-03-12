import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

interface Workflow {
  wf_id: string;
  name: string;
  description: string;
  step_count: number;
  created_at: number;
}

interface WorkflowRun {
  run_id: string;
  wf_id: string;
  status: string;
  started_at: number;
  finished_at: number | null;
  results: Record<string, unknown>;
}

const API = 'http://127.0.0.1:9742';

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, opts);
  return r.json();
}

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      backgroundColor: `${color}22`, color, border: `1px solid ${color}44`,
      textTransform: 'uppercase',
    }}>{text}</span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: COLORS.green, running: COLORS.orange, failed: COLORS.red, pending: COLORS.textDim,
  };
  return <Badge text={status} color={map[status] || COLORS.textDim} />;
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8,
      padding: 16, ...style,
    }}>{children}</div>
  );
}

export default function WorkflowPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<Workflow[]>('/api/workflows');
      setWorkflows(Array.isArray(data) ? data : []);
    } catch { setWorkflows([]); }
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 10000); return () => clearInterval(t); }, [refresh]);

  const handleRun = async (wfId: string) => {
    setLoading(true);
    try {
      await apiFetch('/api/workflows/execute', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wf_id: wfId }),
      });
      await refresh();
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 20, fontFamily: FONT }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: COLORS.text, fontSize: 18, fontWeight: 700, margin: 0 }}>Workflows</h2>
        <span style={{ color: COLORS.textDim, fontSize: 12 }}>{workflows.length} workflow(s)</span>
      </div>

      {workflows.length === 0 ? (
        <Card>
          <p style={{ color: COLORS.textDim, fontSize: 13, textAlign: 'center', margin: '20px 0' }}>
            Aucun workflow. Creez-en via l'API ou MCP.
          </p>
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
          {workflows.map(wf => (
            <Card key={wf.wf_id} style={{ cursor: 'pointer', borderColor: selected === wf.wf_id ? COLORS.orange : COLORS.border }}
              >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ color: COLORS.text, fontWeight: 600, fontSize: 14 }}>{wf.name}</span>
                <span style={{ color: COLORS.textDim, fontSize: 10 }}>{wf.step_count} steps</span>
              </div>
              <p style={{ color: COLORS.textDim, fontSize: 12, margin: '0 0 12px 0' }}>
                {wf.description || 'Pas de description'}
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => handleRun(wf.wf_id)} disabled={loading} style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  backgroundColor: COLORS.orange, color: '#fff', border: 'none', cursor: 'pointer',
                  opacity: loading ? 0.5 : 1,
                }}>Executer</button>
                <button onClick={() => setSelected(selected === wf.wf_id ? null : wf.wf_id)} style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  backgroundColor: 'transparent', color: COLORS.textDim, border: `1px solid ${COLORS.border}`,
                  cursor: 'pointer',
                }}>Details</button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Stats */}
      <Card style={{ marginTop: 20 }}>
        <h3 style={{ color: COLORS.text, fontSize: 14, fontWeight: 700, margin: '0 0 8px 0' }}>Scheduler</h3>
        <SchedulerStats />
      </Card>
    </div>
  );
}

function SchedulerStats() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    apiFetch<Record<string, unknown>>('/api/scheduler/stats').then(setStats).catch(() => {});
  }, []);
  if (!stats) return <span style={{ color: COLORS.textDim, fontSize: 12 }}>Chargement...</span>;
  return (
    <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
      {Object.entries(stats).map(([k, v]) => (
        <div key={k} style={{ textAlign: 'center' }}>
          <div style={{ color: COLORS.orange, fontSize: 18, fontWeight: 700 }}>{String(v)}</div>
          <div style={{ color: COLORS.textDim, fontSize: 10, textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
        </div>
      ))}
    </div>
  );
}
