import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface QueueTask {
  task_id: string;
  name: string;
  priority: number;
  status: string;
  result?: any;
  error?: string;
  retries: number;
}

interface FsmInfo {
  name: string;
  current_state: string;
  states: string[];
  transitions: number;
  available_events: string[];
}

interface LogEntry {
  message: string;
  level: string;
  source: string;
  ts: number;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: COLORS.orange, running: '#60a5fa', completed: COLORS.green, failed: COLORS.red,
  };
  const color = colors[status] || COLORS.textDim;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 3,
      backgroundColor: `${color}22`, color, textTransform: 'uppercase',
    }}>{status}</span>
  );
}

export default function QueuePage() {
  const [tasks, setTasks] = useState<QueueTask[]>([]);
  const [fsms, setFsms] = useState<FsmInfo[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [templateStats, setTemplateStats] = useState<any>(null);

  const refresh = useCallback(async () => {
    try {
      const [tRes, fRes, lRes, tsRes] = await Promise.allSettled([
        fetch(`${API}/api/queue`).then(r => r.json()),
        fetch(`${API}/api/fsm`).then(r => r.json()),
        fetch(`${API}/api/logagg`).then(r => r.json()),
        fetch(`${API}/api/templates/stats`).then(r => r.json()),
      ]);
      if (tRes.status === 'fulfilled') setTasks(Array.isArray(tRes.value) ? tRes.value : []);
      if (fRes.status === 'fulfilled') setFsms(Array.isArray(fRes.value) ? fRes.value : []);
      if (lRes.status === 'fulfilled') setLogs(Array.isArray(lRes.value) ? lRes.value.slice(-20).reverse() : []);
      if (tsRes.status === 'fulfilled') setTemplateStats(tsRes.value);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 8_000);
    return () => clearInterval(iv);
  }, [refresh]);

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 20, fontFamily: FONT, color: COLORS.text }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Queue & State Machines</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      {/* Template Stats + FSM Summary */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        {templateStats && (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 200,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>TEMPLATES</div>
            <div style={{ fontSize: 12 }}>
              {templateStats.total_templates} templates | {templateStats.render_count} renders | {templateStats.global_vars} globals
            </div>
          </div>
        )}
        <div style={{
          backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 200,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>STATE MACHINES</div>
          {fsms.length === 0 ? (
            <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucune FSM</div>
          ) : (
            fsms.map(f => (
              <div key={f.name} style={{ fontSize: 11, marginBottom: 4 }}>
                <span style={{ fontWeight: 600 }}>{f.name}</span>: {f.current_state}
                <span style={{ color: COLORS.textDim }}> ({f.states.length} etats, {f.transitions} transitions)</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Task Queue */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8 }}>TASK QUEUE</h2>
      {tasks.length === 0 ? (
        <div style={{ fontSize: 12, color: COLORS.textDim, marginBottom: 16 }}>File vide</div>
      ) : (
        <div style={{
          backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, marginBottom: 16,
        }}>
          {tasks.map(t => (
            <div key={t.task_id} style={{
              padding: '8px 12px', borderBottom: `1px solid ${COLORS.border}`,
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <StatusBadge status={t.status} />
              <span style={{ fontSize: 12, fontWeight: 600 }}>{t.name}</span>
              <span style={{ fontSize: 10, color: COLORS.textDim }}>P{t.priority}</span>
              {t.retries > 0 && <span style={{ fontSize: 10, color: COLORS.orange }}>R{t.retries}</span>}
              {t.error && <span style={{ fontSize: 10, color: COLORS.red, marginLeft: 'auto' }}>{t.error}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Recent Logs */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8 }}>LOGS RECENTS</h2>
      <div style={{
        backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6,
        maxHeight: 300, overflowY: 'auto', fontFamily: 'monospace',
      }}>
        {logs.length === 0 ? (
          <div style={{ padding: 12, fontSize: 11, color: COLORS.textDim }}>Aucun log</div>
        ) : (
          logs.map((l, i) => (
            <div key={i} style={{
              padding: '4px 10px', borderBottom: `1px solid ${COLORS.border}`, fontSize: 10,
              color: l.level === 'error' ? COLORS.red : l.level === 'warning' ? COLORS.orange : COLORS.textDim,
            }}>
              [{l.level}] {l.source}: {l.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
