import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface ClipItem { content: string; category: string; pinned: boolean; timestamp: number; }
interface HotkeyItem { name: string; keys: string; description: string; enabled: boolean; activation_count: number; group: string; }
interface SnapItem { id: string; name: string; tags: string[]; size: number; timestamp: number; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.purple, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function SnapshotsPage() {
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [hotkeys, setHotkeys] = useState<HotkeyItem[]>([]);
  const [snaps, setSnaps] = useState<SnapItem[]>([]);
  const [clipStats, setClipStats] = useState<Record<string, any>>({});
  const [hkStats, setHkStats] = useState<Record<string, any>>({});
  const [snapStats, setSnapStats] = useState<Record<string, any>>({});

  const refresh = useCallback(async () => {
    try {
      const [r1, r2, r3, r4, r5, r6] = await Promise.all([
        fetch(`${API}/api/clipboard/history`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/hotkeys/list`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/snapshots/list`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/clipboard/stats`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/api/hotkeys/stats`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/api/snapshots/stats`).then(r => r.json()).catch(() => ({})),
      ]);
      if (Array.isArray(r1)) setClips(r1);
      if (Array.isArray(r2)) setHotkeys(r2);
      if (Array.isArray(r3)) setSnaps(r3);
      setClipStats(r4); setHkStats(r5); setSnapStats(r6);
    } catch {}
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [refresh]);

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto', fontFamily: FONT, color: COLORS.text }}>
      <h1 style={{ fontSize: 16, fontWeight: 800, color: COLORS.purple, marginBottom: 16 }}>Snapshots & Controls</h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Clipboard', val: `${clipStats.total_entries || 0} entrees, ${clipStats.pinned || 0} pinned` },
          { label: 'Hotkeys', val: `${hkStats.total_shortcuts || 0} raccourcis, ${hkStats.total_activations || 0} activ.` },
          { label: 'Snapshots', val: `${snapStats.total_snapshots || 0} captures, ${snapStats.total_restores || 0} restores` },
        ].map(s => (
          <div key={s.label} style={{ background: COLORS.surface, borderRadius: 8, padding: 12, border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: 10, color: COLORS.textDim, marginBottom: 4 }}>{s.label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: COLORS.purple }}>{s.val}</div>
          </div>
        ))}
      </div>

      <Section title="CLIPBOARD HISTORY">
        {clips.length === 0 ? <div style={{ fontSize: 12, color: COLORS.textDim }}>Historique vide</div> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {clips.slice(-10).reverse().map((c, i) => (
              <div key={i} style={{ padding: '6px 10px', borderRadius: 6, fontSize: 11, background: COLORS.surface, border: `1px solid ${COLORS.border}`, display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ color: COLORS.cyan, fontSize: 9, minWidth: 36 }}>{c.category}</span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.content}</span>
                {c.pinned && <span style={{ color: COLORS.orange, fontSize: 9 }}>PIN</span>}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="HOTKEYS">
        {hotkeys.length === 0 ? <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun raccourci</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead><tr>{['Nom', 'Keys', 'Description', 'Group', 'Actif', 'Activations'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textDim }}>{h}</th>
            ))}</tr></thead>
            <tbody>{hotkeys.map(hk => (
              <tr key={hk.name}>
                <td style={{ padding: '4px 8px', fontWeight: 600 }}>{hk.name}</td>
                <td style={{ padding: '4px 8px', color: COLORS.cyan }}>{hk.keys}</td>
                <td style={{ padding: '4px 8px', color: COLORS.textDim }}>{hk.description}</td>
                <td style={{ padding: '4px 8px' }}>{hk.group}</td>
                <td style={{ padding: '4px 8px', color: hk.enabled ? COLORS.green : COLORS.red }}>{hk.enabled ? 'Oui' : 'Non'}</td>
                <td style={{ padding: '4px 8px' }}>{hk.activation_count}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Section>

      <Section title="SNAPSHOTS">
        {snaps.length === 0 ? <div style={{ fontSize: 12, color: COLORS.textDim }}>Aucun snapshot</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead><tr>{['ID', 'Nom', 'Tags', 'Taille', 'Date'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textDim }}>{h}</th>
            ))}</tr></thead>
            <tbody>{snaps.map(s => (
              <tr key={s.id}>
                <td style={{ padding: '4px 8px', color: COLORS.textDim }}>{s.id}</td>
                <td style={{ padding: '4px 8px', fontWeight: 600 }}>{s.name}</td>
                <td style={{ padding: '4px 8px' }}>{s.tags.join(', ') || '-'}</td>
                <td style={{ padding: '4px 8px' }}>{s.size}</td>
                <td style={{ padding: '4px 8px', color: COLORS.textDim }}>{new Date(s.timestamp * 1000).toLocaleString()}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </Section>
    </div>
  );
}
