import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface EventItem { id: string; stream: string; type: string; version: number; timestamp: number; }
interface WebhookEP { name: string; url: string; active: boolean; events: string[]; }
interface ProbeItem { name: string; critical: boolean; last_status: string; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color = status === 'healthy' ? COLORS.green : status === 'degraded' ? COLORS.orange : status === 'unhealthy' ? COLORS.red : COLORS.textDim;
  return (
    <span style={{
      fontSize: 9, padding: '1px 6px', borderRadius: 3,
      backgroundColor: `${color}22`, color, fontWeight: 700,
    }}>{status.toUpperCase()}</span>
  );
}

export default function InfraPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [streams, setStreams] = useState<string[]>([]);
  const [webhooks, setWebhooks] = useState<WebhookEP[]>([]);
  const [probes, setProbes] = useState<ProbeItem[]>([]);
  const [evStats, setEvStats] = useState<any>(null);
  const [whStats, setWhStats] = useState<any>(null);
  const [hpStats, setHpStats] = useState<any>(null);

  const refresh = useCallback(async () => {
    try {
      const [evR, stR, whR, prR, esR, wsR, hsR] = await Promise.allSettled([
        fetch(`${API}/api/evstore/events?limit=30`).then(r => r.json()),
        fetch(`${API}/api/evstore/streams`).then(r => r.json()),
        fetch(`${API}/api/webhooks/list`).then(r => r.json()),
        fetch(`${API}/api/healthprobe/list`).then(r => r.json()),
        fetch(`${API}/api/evstore/stats`).then(r => r.json()),
        fetch(`${API}/api/webhooks/stats`).then(r => r.json()),
        fetch(`${API}/api/healthprobe/stats`).then(r => r.json()),
      ]);
      if (evR.status === 'fulfilled') setEvents(Array.isArray(evR.value) ? evR.value : []);
      if (stR.status === 'fulfilled') setStreams(stR.value?.streams || []);
      if (whR.status === 'fulfilled') setWebhooks(Array.isArray(whR.value) ? whR.value : []);
      if (prR.status === 'fulfilled') setProbes(Array.isArray(prR.value) ? prR.value : []);
      if (esR.status === 'fulfilled') setEvStats(esR.value);
      if (wsR.status === 'fulfilled') setWhStats(wsR.value);
      if (hsR.status === 'fulfilled') setHpStats(hsR.value);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10_000);
    return () => clearInterval(iv);
  }, [refresh]);

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 20, fontFamily: FONT, color: COLORS.text }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Infrastructure</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      {/* Health Probes */}
      <Section title="HEALTH PROBES">
        {probes.length === 0 ? (
          <div style={{ fontSize: 11, color: COLORS.textDim }}>Aucune probe enregistree</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
            {probes.map(p => (
              <div key={p.name} style={{
                backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 12, fontWeight: 700 }}>{p.name}</span>
                  <StatusBadge status={p.last_status} />
                </div>
                <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 4 }}>
                  {p.critical ? 'CRITICAL' : 'NON-CRITICAL'}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Event Streams */}
      <Section title="EVENT STREAMS">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          {streams.map(s => (
            <span key={s} style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 3,
              backgroundColor: `${COLORS.purple}15`, color: COLORS.purple, fontWeight: 600,
            }}>{s}</span>
          ))}
          {streams.length === 0 && <span style={{ fontSize: 11, color: COLORS.textDim }}>Aucun stream</span>}
        </div>
        <div style={{
          backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6,
          padding: 10, maxHeight: 200, overflowY: 'auto',
        }}>
          {events.length === 0 ? (
            <div style={{ fontSize: 11, color: COLORS.textDim }}>Aucun evenement</div>
          ) : events.slice(-20).reverse().map(e => (
            <div key={e.id} style={{
              fontSize: 10, padding: '3px 0', borderBottom: `1px solid ${COLORS.border}20`,
              display: 'flex', gap: 8,
            }}>
              <span style={{ color: COLORS.orange, minWidth: 70 }}>{e.stream}</span>
              <span style={{ color: COLORS.textDim, minWidth: 100 }}>{e.type}</span>
              <span style={{ color: COLORS.textDim }}>v{e.version}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* Webhooks */}
      <Section title="WEBHOOKS">
        {webhooks.length === 0 ? (
          <div style={{ fontSize: 11, color: COLORS.textDim }}>Aucun webhook enregistre</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
            {webhooks.map(w => (
              <div key={w.name} style={{
                backgroundColor: COLORS.bgCard, border: `1px solid ${w.active ? COLORS.green : COLORS.border}`,
                borderRadius: 6, padding: 12,
              }}>
                <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 4 }}>{w.name}</div>
                <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 4, wordBreak: 'break-all' }}>{w.url}</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {w.events.length === 0 ? (
                    <span style={{ fontSize: 9, color: COLORS.textDim }}>all events</span>
                  ) : w.events.map(ev => (
                    <span key={ev} style={{
                      fontSize: 9, padding: '1px 5px', borderRadius: 3,
                      backgroundColor: `${COLORS.green}15`, color: COLORS.green,
                    }}>{ev}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {evStats && (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>EVENT STORE</div>
            <div style={{ fontSize: 12 }}>
              {evStats.total_events} events | {evStats.streams} streams | {evStats.snapshots} snapshots
            </div>
          </div>
        )}
        {whStats && (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>WEBHOOKS</div>
            <div style={{ fontSize: 12 }}>
              {whStats.endpoints} endpoints | {whStats.total_deliveries} deliveries | {whStats.success_rate}% success
            </div>
          </div>
        )}
        {hpStats && (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>HEALTH PROBES</div>
            <div style={{ fontSize: 12 }}>
              {hpStats.total_probes} probes | {hpStats.total_checks} checks | {hpStats.overall}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
