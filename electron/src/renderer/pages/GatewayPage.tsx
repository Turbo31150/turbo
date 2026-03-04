import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface RoleInfo { name: string; permissions: string[]; description: string; }
interface EnvProfile { name: string; var_count: number; active: boolean; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function GatewayPage() {
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [envProfiles, setEnvProfiles] = useState<EnvProfile[]>([]);
  const [telemetryStats, setTelemetryStats] = useState<any>(null);
  const [permStats, setPermStats] = useState<any>(null);

  const refresh = useCallback(async () => {
    try {
      const [rRes, eRes, tRes, pRes] = await Promise.allSettled([
        fetch(`${API}/api/permissions/roles`).then(r => r.json()),
        fetch(`${API}/api/env/profiles`).then(r => r.json()),
        fetch(`${API}/api/telemetry/stats`).then(r => r.json()),
        fetch(`${API}/api/permissions/stats`).then(r => r.json()),
      ]);
      if (rRes.status === 'fulfilled') setRoles(Array.isArray(rRes.value) ? rRes.value : []);
      if (eRes.status === 'fulfilled') setEnvProfiles(Array.isArray(eRes.value) ? eRes.value : []);
      if (tRes.status === 'fulfilled') setTelemetryStats(tRes.value);
      if (pRes.status === 'fulfilled') setPermStats(pRes.value);
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
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Gateway & Security</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      {/* RBAC Roles */}
      <Section title="ROLES RBAC">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
          {roles.map(r => (
            <div key={r.name} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{r.name}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 6 }}>{r.description}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {r.permissions.slice(0, 6).map(p => (
                  <span key={p} style={{
                    fontSize: 9, padding: '1px 6px', borderRadius: 3,
                    backgroundColor: `${COLORS.orange}15`, color: COLORS.orange,
                  }}>{p}</span>
                ))}
                {r.permissions.length > 6 && (
                  <span style={{ fontSize: 9, color: COLORS.textDim }}>+{r.permissions.length - 6}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Environment Profiles */}
      <Section title="ENVIRONNEMENTS">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {envProfiles.map(e => (
            <div key={e.name} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${e.active ? COLORS.orange : COLORS.border}`,
              borderRadius: 6, padding: 12, minWidth: 140, textAlign: 'center',
            }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>{e.name.toUpperCase()}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>{e.var_count} variables</div>
              {e.active && (
                <span style={{
                  fontSize: 9, padding: '1px 6px', borderRadius: 3, marginTop: 4, display: 'inline-block',
                  backgroundColor: `${COLORS.green}22`, color: COLORS.green,
                }}>ACTIF</span>
              )}
            </div>
          ))}
        </div>
      </Section>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {permStats && (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 200,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>PERMISSIONS</div>
            <div style={{ fontSize: 12 }}>
              {permStats.total_roles} roles | {permStats.total_users} users | {permStats.check_count} checks | {permStats.denied_count} denied
            </div>
          </div>
        )}
        {telemetryStats && (
          <div style={{
            backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 200,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>TELEMETRIE</div>
            <div style={{ fontSize: 12 }}>
              {telemetryStats.total_points} points | {telemetryStats.counters} counters | {telemetryStats.gauges} gauges | {telemetryStats.histograms} histograms
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
