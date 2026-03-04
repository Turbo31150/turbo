import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface NotifEntry {
  ts: number;
  message: string;
  level: string;
  source: string;
  channels_notified: number;
}

interface SessionEntry {
  session_id: string;
  owner: string;
  status: string;
  activity_count: number;
  created_at: number;
}

interface QueueStats {
  total_tasks: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

interface GwStats {
  total_routes: number;
  enabled_routes: number;
  total_clients: number;
  total_requests: number;
  total_errors: number;
}

function LevelBadge({ level }: { level: string }) {
  const colorMap: Record<string, string> = {
    info: COLORS.blue || '#60a5fa', warning: COLORS.orange, critical: COLORS.red, debug: COLORS.textDim,
  };
  const color = colorMap[level] || COLORS.textDim;
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 3,
      backgroundColor: `${color}22`, color, textTransform: 'uppercase',
    }}>{level}</span>
  );
}

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6,
      padding: 12, textAlign: 'center', minWidth: 100,
    }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || COLORS.orange }}>{value}</div>
      <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 2 }}>{label}</div>
    </div>
  );
}

export default function NotificationsPage() {
  const [history, setHistory] = useState<NotifEntry[]>([]);
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
  const [gwStats, setGwStats] = useState<GwStats | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [hRes, sRes, qRes, gRes] = await Promise.allSettled([
        fetch(`${API}/api/notifications/history`).then(r => r.json()),
        fetch(`${API}/api/sessions_v2`).then(r => r.json()),
        fetch(`${API}/api/queue/stats`).then(r => r.json()),
        fetch(`${API}/api/gateway/stats`).then(r => r.json()),
      ]);
      if (hRes.status === 'fulfilled') setHistory(Array.isArray(hRes.value) ? hRes.value.slice(-30).reverse() : []);
      if (sRes.status === 'fulfilled') setSessions(Array.isArray(sRes.value) ? sRes.value : []);
      if (qRes.status === 'fulfilled') setQueueStats(qRes.value);
      if (gRes.status === 'fulfilled') setGwStats(gRes.value);
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
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Notifications & Queue</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        {queueStats && (
          <>
            <StatCard label="Queue Pending" value={queueStats.pending} />
            <StatCard label="Queue Running" value={queueStats.running} color={COLORS.green} />
            <StatCard label="Queue Completed" value={queueStats.completed} color={COLORS.green} />
            <StatCard label="Queue Failed" value={queueStats.failed} color={COLORS.red} />
          </>
        )}
        {gwStats && (
          <>
            <StatCard label="GW Routes" value={gwStats.total_routes} />
            <StatCard label="GW Requests" value={gwStats.total_requests} />
            <StatCard label="GW Errors" value={gwStats.total_errors} color={COLORS.red} />
          </>
        )}
      </div>

      {/* Active Sessions */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>SESSIONS ACTIVES</h2>
      {sessions.length === 0 ? (
        <div style={{ fontSize: 12, color: COLORS.textDim, marginBottom: 16 }}>Aucune session</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10, marginBottom: 20 }}>
          {sessions.map(s => (
            <div key={s.session_id} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 10,
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>{s.owner}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>ID: {s.session_id}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>
                Status: {s.status} | Activity: {s.activity_count}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Notification History */}
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>HISTORIQUE NOTIFICATIONS</h2>
      <div style={{
        backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6,
        maxHeight: 400, overflowY: 'auto',
      }}>
        {history.length === 0 ? (
          <div style={{ padding: 12, fontSize: 12, color: COLORS.textDim }}>Aucune notification</div>
        ) : (
          history.map((n, i) => (
            <div key={i} style={{
              padding: '8px 12px', borderBottom: `1px solid ${COLORS.border}`,
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <LevelBadge level={n.level} />
              <span style={{ fontSize: 11, flex: 1 }}>{n.message}</span>
              <span style={{ fontSize: 9, color: COLORS.textDim }}>{n.source}</span>
              <span style={{ fontSize: 9, color: COLORS.textDim }}>
                {new Date(n.ts * 1000).toLocaleTimeString()}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
