import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface ServiceEntry {
  name: string;
  url: string;
  service_type: string;
  health_status: string;
  heartbeat_count: number;
  registered_at?: number;
  last_heartbeat?: number;
}

interface NotifChannel {
  name: string;
  type: string;
  min_level: string;
  enabled: boolean;
  sent_count: number;
  error_count: number;
}

interface FlagEntry {
  name: string;
  enabled: boolean;
  description: string;
  percentage: number;
  check_count: number;
}

function StatusBadge({ status }: { status: string }) {
  const color = status === 'healthy' ? COLORS.green : status === 'degraded' ? COLORS.orange : COLORS.red;
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      backgroundColor: `${color}22`, color, border: `1px solid ${color}44`,
      textTransform: 'uppercase',
    }}>{status}</span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function ServicesPage() {
  const [services, setServices] = useState<ServiceEntry[]>([]);
  const [channels, setChannels] = useState<NotifChannel[]>([]);
  const [flags, setFlags] = useState<FlagEntry[]>([]);
  const [backupStats, setBackupStats] = useState<any>(null);

  const refresh = useCallback(async () => {
    try {
      const [sRes, cRes, fRes, bRes] = await Promise.allSettled([
        fetch(`${API}/api/services`).then(r => r.json()),
        fetch(`${API}/api/notifications/channels`).then(r => r.json()),
        fetch(`${API}/api/flags`).then(r => r.json()),
        fetch(`${API}/api/backups/stats`).then(r => r.json()),
      ]);
      if (sRes.status === 'fulfilled') setServices(Array.isArray(sRes.value) ? sRes.value : []);
      if (cRes.status === 'fulfilled') setChannels(Array.isArray(cRes.value) ? cRes.value : []);
      if (fRes.status === 'fulfilled') setFlags(Array.isArray(fRes.value) ? fRes.value : []);
      if (bRes.status === 'fulfilled') setBackupStats(bRes.value);
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
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Services & Infrastructure</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      {/* Service Registry */}
      <Section title="SERVICE REGISTRY">
        {services.length === 0 ? (
          <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun service enregistre</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
            {services.map(s => (
              <div key={s.name} style={{
                backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{s.name}</span>
                  <StatusBadge status={s.health_status} />
                </div>
                <div style={{ fontSize: 11, color: COLORS.textDim }}>{s.url}</div>
                <div style={{ fontSize: 10, color: COLORS.textDim, marginTop: 4 }}>
                  Type: {s.service_type} | Heartbeats: {s.heartbeat_count}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Notification Channels */}
      <Section title="NOTIFICATION CHANNELS">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
          {channels.map(ch => (
            <div key={ch.name} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 10,
              opacity: ch.enabled ? 1 : 0.5,
            }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>{ch.name}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>
                Type: {ch.type} | Level: {ch.min_level}
              </div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>
                Sent: {ch.sent_count} | Errors: {ch.error_count}
              </div>
              <span style={{
                fontSize: 9, padding: '1px 6px', borderRadius: 3, marginTop: 4, display: 'inline-block',
                backgroundColor: ch.enabled ? `${COLORS.green}22` : `${COLORS.red}22`,
                color: ch.enabled ? COLORS.green : COLORS.red,
              }}>{ch.enabled ? 'ACTIF' : 'INACTIF'}</span>
            </div>
          ))}
        </div>
      </Section>

      {/* Feature Flags */}
      <Section title="FEATURE FLAGS">
        {flags.length === 0 ? (
          <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun flag configure</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10 }}>
            {flags.map(f => (
              <div key={f.name} style={{
                backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 10,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontSize: 12, fontWeight: 600 }}>{f.name}</span>
                  <span style={{
                    fontSize: 9, padding: '1px 6px', borderRadius: 3,
                    backgroundColor: f.enabled ? `${COLORS.green}22` : `${COLORS.red}22`,
                    color: f.enabled ? COLORS.green : COLORS.red,
                  }}>{f.enabled ? 'ON' : 'OFF'}</span>
                </div>
                <div style={{ fontSize: 10, color: COLORS.textDim }}>
                  {f.description || 'No description'} | Rollout: {f.percentage}% | Checks: {f.check_count}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Backup Stats */}
      <Section title="BACKUP MANAGER">
        {backupStats ? (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12,
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
          }}>
            {[
              { label: 'Total', value: backupStats.total_backups },
              { label: 'Completed', value: backupStats.completed },
              { label: 'Failed', value: backupStats.failed },
              { label: 'Size', value: `${backupStats.total_size_mb} MB` },
            ].map(s => (
              <div key={s.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: COLORS.orange }}>{s.value}</div>
                <div style={{ fontSize: 10, color: COLORS.textDim }}>{s.label}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: COLORS.textDim }}>Chargement...</div>
        )}
      </Section>
    </div>
  );
}
