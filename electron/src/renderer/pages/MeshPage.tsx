import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface ServiceInst { service_id: string; name: string; host: string; port: number; status: string; active_connections: number; }
interface RuleItem { name: string; priority: number; group: string; enabled: boolean; description: string; fire_count: number; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function MeshPage() {
  const [services, setServices] = useState<ServiceInst[]>([]);
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [meshStats, setMeshStats] = useState<any>(null);
  const [vaultStats, setVaultStats] = useState<any>(null);
  const [rulesStats, setRulesStats] = useState<any>(null);

  const refresh = useCallback(async () => {
    try {
      const [sR, rR, msR, vsR, rsR] = await Promise.allSettled([
        fetch(`${API}/api/mesh/services`).then(r => r.json()),
        fetch(`${API}/api/rules/list`).then(r => r.json()),
        fetch(`${API}/api/mesh/stats`).then(r => r.json()),
        fetch(`${API}/api/vault/stats`).then(r => r.json()),
        fetch(`${API}/api/rules/stats`).then(r => r.json()),
      ]);
      if (sR.status === 'fulfilled') setServices(Array.isArray(sR.value) ? sR.value : []);
      if (rR.status === 'fulfilled') setRules(Array.isArray(rR.value) ? rR.value : []);
      if (msR.status === 'fulfilled') setMeshStats(msR.value);
      if (vsR.status === 'fulfilled') setVaultStats(vsR.value);
      if (rsR.status === 'fulfilled') setRulesStats(rsR.value);
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
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Service Mesh & Rules</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      {/* Service Instances */}
      <Section title="SERVICE MESH">
        {services.length === 0 ? (
          <div style={{ fontSize: 11, color: COLORS.textDim }}>Aucune instance enregistree</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
            {services.map(s => {
              const statusColor = s.status === 'healthy' ? COLORS.green : s.status === 'degraded' ? COLORS.orange : COLORS.red;
              return (
                <div key={s.service_id} style={{
                  backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 700 }}>{s.name}</span>
                    <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, backgroundColor: `${statusColor}22`, color: statusColor }}>{s.status.toUpperCase()}</span>
                  </div>
                  <div style={{ fontSize: 10, color: COLORS.textDim }}>{s.host}:{s.port}</div>
                  <div style={{ fontSize: 10, color: COLORS.textDim }}>{s.active_connections} connections</div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {/* Rules */}
      <Section title="MOTEUR DE REGLES">
        {rules.length === 0 ? (
          <div style={{ fontSize: 11, color: COLORS.textDim }}>Aucune regle configuree</div>
        ) : (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 10 }}>
            {rules.map(r => (
              <div key={r.name} style={{
                padding: '6px 0', borderBottom: `1px solid ${COLORS.border}20`,
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <span style={{ fontSize: 11, fontWeight: 700, minWidth: 120 }}>{r.name}</span>
                <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, backgroundColor: `${COLORS.purple}15`, color: COLORS.purple }}>{r.group}</span>
                <span style={{ fontSize: 10, color: COLORS.textDim }}>P{r.priority}</span>
                <span style={{ fontSize: 10, color: r.enabled ? COLORS.green : COLORS.red }}>{r.enabled ? 'ON' : 'OFF'}</span>
                <span style={{ fontSize: 10, color: COLORS.textDim, marginLeft: 'auto' }}>{r.fire_count} fires</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {meshStats && (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>MESH</div>
            <div style={{ fontSize: 12 }}>
              {meshStats.total_instances} instances | {meshStats.healthy} healthy | {meshStats.active_connections} conns
            </div>
          </div>
        )}
        {vaultStats && (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>VAULT</div>
            <div style={{ fontSize: 12 }}>
              {vaultStats.total_secrets} secrets | {vaultStats.namespaces} namespaces | {vaultStats.total_access_count} accesses
            </div>
          </div>
        )}
        {rulesStats && (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>RULES</div>
            <div style={{ fontSize: 12 }}>
              {rulesStats.total_rules} rules | {rulesStats.enabled} enabled | {rulesStats.total_fires} fires
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
