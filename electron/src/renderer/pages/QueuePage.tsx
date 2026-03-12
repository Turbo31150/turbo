import React, { useState, useEffect, useCallback, useRef } from 'react';
import { COLORS, FONT, NODE_COLORS } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

/* ── Types ─────────────────────────────────────────────────────────── */

interface TaskItem {
  id: string;
  prompt: string;
  task_type: string;
  priority: number;
  status: string;
  node: string;
  result: string;
  error: string;
  retries: number;
  max_retries: number;
  created_at: number;
  finished_at: number;
}

interface QueueStats {
  total: number;
  by_status: Record<string, number>;
  processing: boolean;
  pending: TaskItem[];
  recent: TaskItem[];
}

interface AutomationStatus {
  running: boolean;
  uptime_s: number;
  autonomous_loop?: { running: boolean; task_count: number; event_count: number };
  task_scheduler?: { total_jobs: number; enabled_jobs: number };
}

interface SelfImproveStatus {
  cycles: number;
  total_actions: number;
  last_report?: { actions: { type: string; target: string; desc: string }[] };
}

interface SingletonMap {
  [name: string]: { pid: number; alive: boolean };
}

/* ── Helpers ───────────────────────────────────────────────────────── */

function StatusBadge({ status }: { status: string }) {
  const c: Record<string, string> = {
    pending: COLORS.orange, running: COLORS.blue, done: COLORS.green,
    failed: COLORS.red, cancelled: COLORS.textDim,
  };
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '2px 7px', borderRadius: 3,
      backgroundColor: `${c[status] || COLORS.textDim}22`,
      color: c[status] || COLORS.textDim, textTransform: 'uppercase',
    }}>{status}</span>
  );
}

function NodeBadge({ node }: { node: string }) {
  const color = NODE_COLORS[node] || COLORS.textDim;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 3,
      backgroundColor: `${color}22`, color,
    }}>{node}</span>
  );
}

function StatCard({ label, value, color, sub }: { label: string; value: string | number; color: string; sub?: string }) {
  return (
    <div style={{
      backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`,
      borderRadius: 8, padding: '12px 16px', flex: 1, minWidth: 120,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: COLORS.textDim, marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

/* ── Main ──────────────────────────────────────────────────────────── */

export default function QueuePage() {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [automation, setAutomation] = useState<AutomationStatus | null>(null);
  const [selfImprove, setSelfImprove] = useState<SelfImproveStatus | null>(null);
  const [singletons, setSingletons] = useState<SingletonMap>({});
  const [tab, setTab] = useState<'pending' | 'recent'>('pending');

  // New task form
  const [prompt, setPrompt] = useState('');
  const [taskType, setTaskType] = useState('code');
  const [priority, setPriority] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState('');
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const refresh = useCallback(async () => {
    const [qRes, aRes, siRes, sgRes] = await Promise.allSettled([
      fetch(`${API}/api/queue/status`).then(r => r.json()),
      fetch(`${API}/api/automation/status`).then(r => r.json()),
      fetch(`${API}/api/self-improve/status`).then(r => r.json()),
      fetch(`${API}/api/singletons/list`).then(r => r.json()),
    ]);
    if (qRes.status === 'fulfilled') setStats(qRes.value);
    if (aRes.status === 'fulfilled') setAutomation(aRes.value);
    if (siRes.status === 'fulfilled') setSelfImprove(siRes.value);
    if (sgRes.status === 'fulfilled') setSingletons(sgRes.value);
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 5_000);
    return () => clearInterval(iv);
  }, [refresh]);

  const enqueue = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/queue/enqueue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), task_type: taskType, priority }),
      });
      const data = await r.json();
      if (data.ok) {
        setToast(`Tache ${data.task_id} ajoutee`);
        setPrompt('');
        refresh();
      } else {
        setToast(`Erreur: ${data.error}`);
      }
    } catch (e: any) {
      setToast(`Erreur: ${e.message}`);
    }
    setSubmitting(false);
    setTimeout(() => setToast(''), 4000);
  };

  const triggerSelfImprove = async () => {
    try {
      await fetch(`${API}/api/self-improve/run`, { method: 'POST' });
      setToast('Self-improve cycle lance');
      setTimeout(() => { setToast(''); refresh(); }, 2000);
    } catch { setToast('Erreur self-improve'); }
  };

  const byStatus = stats?.by_status || {};
  const total = stats?.total || 0;
  const pending = byStatus['pending'] || 0;
  const done = byStatus['done'] || 0;
  const failed = byStatus['failed'] || 0;
  const successRate = total > 0 ? Math.round((done / total) * 100) : 0;

  const aliveSingletons = Object.entries(singletons).filter(([, v]) => v.alive);

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 20, fontFamily: FONT, color: COLORS.text }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Cluster Task Queue</h1>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          backgroundColor: automation?.running ? COLORS.green : COLORS.red,
        }} />
        <span style={{ fontSize: 10, color: COLORS.textDim }}>
          {automation?.running ? 'Automation ON' : 'Automation OFF'}
          {automation?.uptime_s ? ` | ${Math.round(automation.uptime_s / 60)}min uptime` : ''}
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={triggerSelfImprove} style={{
            background: 'none', border: `1px solid ${COLORS.purple}44`, color: COLORS.purple,
            padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 10,
          }}>Self-Improve</button>
          <button onClick={refresh} style={{
            background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
            padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 10,
          }}>Refresh</button>
        </div>
      </div>

      {/* Stats Row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <StatCard label="Total" value={total} color={COLORS.text} />
        <StatCard label="Done" value={done} color={COLORS.green} sub={`${successRate}% success`} />
        <StatCard label="Pending" value={pending} color={COLORS.orange} />
        <StatCard label="Failed" value={failed} color={COLORS.red} />
        <StatCard label="Self-Improve" value={selfImprove?.cycles || 0} color={COLORS.purple} sub={`${selfImprove?.total_actions || 0} actions`} />
        <StatCard label="Services" value={aliveSingletons.length} color={COLORS.cyan} sub={aliveSingletons.map(([n]) => n).join(', ')} />
      </div>

      {/* Cluster Nodes */}
      <div style={{
        display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap',
      }}>
        {['M1', 'OL1', 'M3', 'M2'].map(node => {
          const nodeColor = NODE_COLORS[node] || COLORS.textDim;
          const nodeStats = stats?.recent?.filter(t => t.node === node) || [];
          const nodeDone = nodeStats.filter(t => t.status === 'done').length;
          return (
            <div key={node} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${nodeColor}33`,
              borderRadius: 8, padding: '8px 14px', minWidth: 100,
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: nodeColor }}>{node}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>
                {nodeDone} recent done
              </div>
            </div>
          );
        })}
      </div>

      {/* New Task Form */}
      <div style={{
        backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`,
        borderRadius: 8, padding: 14, marginBottom: 16,
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 8 }}>NOUVELLE TACHE</div>
        <textarea
          ref={promptRef}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Decris la tache pour le cluster..."
          onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) enqueue(); }}
          style={{
            width: '100%', minHeight: 60, backgroundColor: COLORS.bgInput,
            border: `1px solid ${COLORS.border}`, borderRadius: 4, color: COLORS.text,
            padding: 8, fontSize: 11, fontFamily: FONT, resize: 'vertical',
          }}
        />
        <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
          <select value={taskType} onChange={e => setTaskType(e.target.value)} style={{
            backgroundColor: COLORS.bgInput, border: `1px solid ${COLORS.border}`,
            color: COLORS.text, padding: '4px 8px', borderRadius: 4, fontSize: 10,
          }}>
            {['code', 'code_fix', 'code_improve', 'test', 'security', 'architecture', 'monitoring', 'cleanup'].map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select value={priority} onChange={e => setPriority(Number(e.target.value))} style={{
            backgroundColor: COLORS.bgInput, border: `1px solid ${COLORS.border}`,
            color: COLORS.text, padding: '4px 8px', borderRadius: 4, fontSize: 10,
          }}>
            {[1, 2, 3, 4, 5].map(p => (
              <option key={p} value={p}>P{p}</option>
            ))}
          </select>
          <button onClick={enqueue} disabled={submitting || !prompt.trim()} style={{
            backgroundColor: COLORS.orange, color: '#000', border: 'none',
            padding: '5px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
            fontWeight: 700, opacity: submitting || !prompt.trim() ? 0.5 : 1,
          }}>
            {submitting ? 'Envoi...' : 'Envoyer au Cluster'}
          </button>
          <span style={{ fontSize: 10, color: COLORS.textDim, marginLeft: 4 }}>Ctrl+Enter</span>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 20, right: 20, backgroundColor: COLORS.bgCard,
          border: `1px solid ${COLORS.orange}`, borderRadius: 6, padding: '8px 16px',
          fontSize: 11, color: COLORS.orange, zIndex: 999,
        }}>{toast}</div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
        {(['pending', 'recent'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? `${COLORS.orange}22` : 'none',
            border: `1px solid ${tab === t ? COLORS.orange : COLORS.border}`,
            color: tab === t ? COLORS.orange : COLORS.textDim,
            padding: '4px 14px', borderRadius: 4, cursor: 'pointer', fontSize: 10,
            fontWeight: tab === t ? 700 : 400, textTransform: 'uppercase',
          }}>{t} ({t === 'pending' ? (stats?.pending?.length || 0) : (stats?.recent?.length || 0)})</button>
        ))}
      </div>

      {/* Task List */}
      <div style={{
        backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8,
      }}>
        {(tab === 'pending' ? stats?.pending : stats?.recent)?.map(t => (
          <div key={t.id} style={{
            padding: '10px 14px', borderBottom: `1px solid ${COLORS.border}`,
            display: 'flex', alignItems: 'flex-start', gap: 8,
          }}>
            <StatusBadge status={t.status} />
            {t.node && <NodeBadge node={t.node} />}
            <span style={{ fontSize: 10, color: COLORS.textDim, fontWeight: 700 }}>P{t.priority}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, lineHeight: 1.4 }}>{t.prompt.slice(0, 120)}{t.prompt.length > 120 ? '...' : ''}</div>
              <div style={{ fontSize: 9, color: COLORS.textDim, marginTop: 2 }}>
                [{t.task_type}] {t.id}
                {t.retries > 0 && <span style={{ color: COLORS.orange }}> R{t.retries}/{t.max_retries}</span>}
                {t.error && <span style={{ color: COLORS.red }}> {t.error.slice(0, 60)}</span>}
              </div>
            </div>
          </div>
        )) || (
          <div style={{ padding: 16, fontSize: 11, color: COLORS.textDim, textAlign: 'center' }}>
            {tab === 'pending' ? 'Aucune tache en attente' : 'Aucune tache recente'}
          </div>
        )}
      </div>

      {/* Self-Improve Actions */}
      {selfImprove?.last_report?.actions && selfImprove.last_report.actions.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.purple, marginBottom: 6 }}>SELF-IMPROVE (dernier cycle)</div>
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8,
          }}>
            {selfImprove.last_report.actions.map((a, i) => (
              <div key={i} style={{
                padding: '6px 12px', borderBottom: `1px solid ${COLORS.border}`,
                fontSize: 10, display: 'flex', gap: 8,
              }}>
                <span style={{ color: COLORS.purple, fontWeight: 700 }}>{a.type}</span>
                <span style={{ color: COLORS.textDim }}>{a.target}</span>
                <span>{a.desc}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
