import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface ProcItem { name: string; command: string; status: string; pid: number | null; group: string; restart_count: number; uptime: number | null; }
interface WatchItem { name: string; directory: string; patterns: string[]; enabled: boolean; files_tracked: number; group: string; }
interface SchemaItem { name: string; fields: number; required: number; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.cyan, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function ProcessesPage() {
  const [processes, setProcesses] = useState<ProcItem[]>([]);
  const [watches, setWatches] = useState<WatchItem[]>([]);
  const [schemas, setSchemas] = useState<SchemaItem[]>([]);
  const [procStats, setProcStats] = useState<Record<string, any>>({});
  const [fwStats, setFwStats] = useState<Record<string, any>>({});
  const [valStats, setValStats] = useState<Record<string, any>>({});

  const refresh = useCallback(async () => {
    try {
      const [r1, r2, r3, r4, r5, r6] = await Promise.all([
        fetch(`${API}/api/processes/list`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/filewatcher/list`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/validator/schemas`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/processes/stats`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/api/filewatcher/stats`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/api/validator/stats`).then(r => r.json()).catch(() => ({})),
      ]);
      if (Array.isArray(r1)) setProcesses(r1);
      if (Array.isArray(r2)) setWatches(r2);
      if (Array.isArray(r3)) setSchemas(r3);
      setProcStats(r4); setFwStats(r5); setValStats(r6);
    } catch {}
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [refresh]);

  const statusColor = (s: string) => s === 'running' ? COLORS.green : s === 'crashed' ? COLORS.red : COLORS.textDim;

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', fontFamily: FONT, color: COLORS.text }}>
      <h1 style={{ fontSize: 16, fontWeight: 800, color: COLORS.cyan, marginBottom: 16 }}>Processes & Monitoring</h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Processus', val: `${procStats.running || 0}/${procStats.total_processes || 0} running` },
          { label: 'Watches', val: `${fwStats.enabled || 0} actifs, ${fwStats.total_files_tracked || 0} fichiers` },
          { label: 'Validations', val: `${valStats.passed || 0}/${valStats.total_validations || 0} OK (${valStats.pass_rate || 0}%)` },
        ].map(s => (
          <div key={s.label} style={{ background: COLORS.surface, borderRadius: 8, padding: 12, border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 4 }}>{s.label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: COLORS.cyan }}>{s.val}</div>
          </div>
        ))}
      </div>

      <Section title="PROCESSUS MANAGES">
        {processes.length === 0 ? <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun processus enregistre</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead><tr>{['Nom', 'Commande', 'Status', 'PID', 'Group', 'Restarts', 'Uptime'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textDim }}>{h}</th>
            ))}</tr></thead>
            <tbody>{processes.map(p => (
              <tr key={p.name}>
                <td style={{ padding: '4px 8px', fontWeight: 600 }}>{p.name}</td>
                <td style={{ padding: '4px 8px', color: COLORS.textDim }}>{p.command}</td>
                <td style={{ padding: '4px 8px', color: statusColor(p.status), fontWeight: 700 }}>{p.status}</td>
                <td style={{ padding: '4px 8px' }}>{p.pid ?? '-'}</td>
                <td style={{ padding: '4px 8px' }}>{p.group}</td>
                <td style={{ padding: '4px 8px' }}>{p.restart_count}</td>
                <td style={{ padding: '4px 8px' }}>{p.uptime ? `${Math.round(p.uptime)}s` : '-'}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Section>

      <Section title="FILE WATCHES">
        {watches.length === 0 ? <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun watch actif</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead><tr>{['Nom', 'Repertoire', 'Patterns', 'Fichiers', 'Group', 'Actif'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textDim }}>{h}</th>
            ))}</tr></thead>
            <tbody>{watches.map(w => (
              <tr key={w.name}>
                <td style={{ padding: '4px 8px', fontWeight: 600 }}>{w.name}</td>
                <td style={{ padding: '4px 8px', color: COLORS.textDim }}>{w.directory}</td>
                <td style={{ padding: '4px 8px' }}>{w.patterns.join(', ')}</td>
                <td style={{ padding: '4px 8px' }}>{w.files_tracked}</td>
                <td style={{ padding: '4px 8px' }}>{w.group}</td>
                <td style={{ padding: '4px 8px', color: w.enabled ? COLORS.green : COLORS.red }}>{w.enabled ? 'Oui' : 'Non'}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Section>

      <Section title="SCHEMAS VALIDATION">
        {schemas.length === 0 ? <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun schema enregistre</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead><tr>{['Schema', 'Champs', 'Requis'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textDim }}>{h}</th>
            ))}</tr></thead>
            <tbody>{schemas.map(s => (
              <tr key={s.name}>
                <td style={{ padding: '4px 8px', fontWeight: 600 }}>{s.name}</td>
                <td style={{ padding: '4px 8px' }}>{s.fields}</td>
                <td style={{ padding: '4px 8px' }}>{s.required}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Section>
    </div>
  );
}
