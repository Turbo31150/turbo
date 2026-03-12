import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface PolicyItem { name: string; max_attempts: number; backoff: string; base_delay: number; }
interface CmdItem { name: string; category: string; description: string; enabled: boolean; exec_count: number; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.orange, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function AutomationPage() {
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [commands, setCommands] = useState<CmdItem[]>([]);
  const [retryStats, setRetryStats] = useState<any>(null);
  const [brokerStats, setBrokerStats] = useState<any>(null);
  const [cmdStats, setCmdStats] = useState<any>(null);

  const refresh = useCallback(async () => {
    try {
      const [pR, cR, rsR, bsR, csR] = await Promise.allSettled([
        fetch(`${API}/api/retry/policies`).then(r => r.json()),
        fetch(`${API}/api/commands/list`).then(r => r.json()),
        fetch(`${API}/api/retry/stats`).then(r => r.json()),
        fetch(`${API}/api/broker/stats`).then(r => r.json()),
        fetch(`${API}/api/commands/stats`).then(r => r.json()),
      ]);
      if (pR.status === 'fulfilled') setPolicies(Array.isArray(pR.value) ? pR.value : []);
      if (cR.status === 'fulfilled') setCommands(Array.isArray(cR.value) ? cR.value : []);
      if (rsR.status === 'fulfilled') setRetryStats(rsR.value);
      if (bsR.status === 'fulfilled') setBrokerStats(bsR.value);
      if (csR.status === 'fulfilled') setCmdStats(csR.value);
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
        <h1 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Automation</h1>
        <button onClick={refresh} style={{
          background: 'none', border: `1px solid ${COLORS.border}`, color: COLORS.textDim,
          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
        }}>Refresh</button>
      </div>

      <Section title="RETRY POLICIES">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {policies.map(p => (
            <div key={p.name} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, minWidth: 180,
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 4 }}>{p.name}</div>
              <div style={{ fontSize: 10, color: COLORS.textDim }}>{p.backoff} | {p.max_attempts} attempts | {p.base_delay}s base</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="COMMANDES">
        {commands.length === 0 ? (
          <div style={{ fontSize: 11, color: COLORS.textDim }}>Aucune commande enregistree</div>
        ) : (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 10 }}>
            {commands.map(c => (
              <div key={c.name} style={{ padding: '5px 0', borderBottom: `1px solid ${COLORS.border}20`, display: 'flex', gap: 10, alignItems: 'center' }}>
                <span style={{ fontSize: 11, fontWeight: 700, minWidth: 120 }}>{c.name}</span>
                <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, backgroundColor: `${COLORS.purple}15`, color: COLORS.purple }}>{c.category}</span>
                <span style={{ fontSize: 10, color: c.enabled ? COLORS.green : COLORS.red }}>{c.enabled ? 'ON' : 'OFF'}</span>
                <span style={{ fontSize: 10, color: COLORS.textDim, marginLeft: 'auto' }}>{c.exec_count}x</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {retryStats && (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>RETRY</div>
            <div style={{ fontSize: 12 }}>{retryStats.total_executions} execs | {retryStats.success_rate}% success</div>
          </div>
        )}
        {brokerStats && (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>BROKER</div>
            <div style={{ fontSize: 12 }}>{brokerStats.topics} topics | {brokerStats.total_messages} msgs | {brokerStats.dlq_size} DLQ</div>
          </div>
        )}
        {cmdStats && (
          <div style={{ backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 6, padding: 12, flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.orange, marginBottom: 6 }}>COMMANDS</div>
            <div style={{ fontSize: 12 }}>{cmdStats.total_commands} cmds | {cmdStats.total_executions} execs</div>
          </div>
        )}
      </div>
    </div>
  );
}
