import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface WinItem { hwnd: number; title: string; class_name: string; visible: boolean; x: number; y: number; width: number; height: number; pid: number; }
interface PowerEvent { action: string; timestamp: number; success: boolean; detail: string; }
interface DlItem { id: string; url: string; filename: string; status: string; progress: number; size_bytes: number; speed_bps: number; error: string; }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, color: COLORS.purple, marginBottom: 8, letterSpacing: 1 }}>{title}</h2>
      {children}
    </div>
  );
}

export default function SystemPage() {
  const [windows, setWindows] = useState<WinItem[]>([]);
  const [powerEvents, setPowerEvents] = useState<PowerEvent[]>([]);
  const [downloads, setDownloads] = useState<DlItem[]>([]);
  const [winStats, setWinStats] = useState<Record<string, any>>({});
  const [pwrStats, setPwrStats] = useState<Record<string, any>>({});
  const [dlStats, setDlStats] = useState<Record<string, any>>({});

  const refresh = useCallback(async () => {
    try {
      const [r1, r2, r3, r4, r5, r6] = await Promise.all([
        fetch(`${API}/api/windows/list`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/power/events`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/downloads/list`).then(r => r.json()).catch(() => []),
        fetch(`${API}/api/windows/stats`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/api/power/stats`).then(r => r.json()).catch(() => ({})),
        fetch(`${API}/api/downloads/stats`).then(r => r.json()).catch(() => ({})),
      ]);
      setWindows(Array.isArray(r1) ? r1 : []);
      setPowerEvents(Array.isArray(r2) ? r2 : []);
      setDownloads(Array.isArray(r3) ? r3 : []);
      setWinStats(r4); setPwrStats(r5); setDlStats(r6);
    } catch {}
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 8000); return () => clearInterval(t); }, [refresh]);

  const th: React.CSSProperties = { textAlign: 'left', padding: '4px 10px', color: COLORS.muted, fontSize: 11, fontFamily: FONT, borderBottom: `1px solid ${COLORS.border}` };
  const td: React.CSSProperties = { padding: '4px 10px', fontSize: 12, fontFamily: FONT, color: COLORS.text, borderBottom: `1px solid ${COLORS.border}` };

  return (
    <div style={{ padding: 24, fontFamily: FONT, color: COLORS.text, overflowY: 'auto', height: '100%' }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: COLORS.cyan, marginBottom: 16 }}>System Control</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Open Windows', value: winStats.open_windows ?? '-', color: COLORS.cyan },
          { label: 'Power Events', value: pwrStats.total_events ?? '-', color: COLORS.yellow },
          { label: 'Downloads', value: dlStats.total_downloads ?? '-', color: COLORS.green },
        ].map(s => (
          <div key={s.label} style={{ background: COLORS.surface, borderRadius: 8, padding: 14, border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>{s.label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      <Section title="OPEN WINDOWS">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr><th style={th}>Title</th><th style={th}>Class</th><th style={th}>PID</th><th style={th}>Position</th><th style={th}>Size</th></tr></thead>
          <tbody>
            {windows.slice(0, 30).map(w => (
              <tr key={w.hwnd}><td style={td}>{w.title.slice(0, 60)}</td><td style={td}>{w.class_name}</td><td style={td}>{w.pid}</td><td style={td}>{w.x},{w.y}</td><td style={td}>{w.width}x{w.height}</td></tr>
            ))}
            {windows.length === 0 && <tr><td style={td} colSpan={5}>No windows</td></tr>}
          </tbody>
        </table>
      </Section>

      <Section title="POWER EVENTS">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr><th style={th}>Action</th><th style={th}>Success</th><th style={th}>Detail</th><th style={th}>Time</th></tr></thead>
          <tbody>
            {powerEvents.slice(-20).reverse().map((e, i) => (
              <tr key={i}><td style={td}>{e.action}</td><td style={{ ...td, color: e.success ? COLORS.green : COLORS.red }}>{e.success ? 'OK' : 'FAIL'}</td><td style={td}>{e.detail}</td><td style={td}>{new Date(e.timestamp * 1000).toLocaleTimeString()}</td></tr>
            ))}
            {powerEvents.length === 0 && <tr><td style={td} colSpan={4}>No events</td></tr>}
          </tbody>
        </table>
      </Section>

      <Section title="DOWNLOADS">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr><th style={th}>File</th><th style={th}>Status</th><th style={th}>Progress</th><th style={th}>Size</th><th style={th}>Speed</th></tr></thead>
          <tbody>
            {downloads.map(d => (
              <tr key={d.id}>
                <td style={td}>{d.filename}</td>
                <td style={{ ...td, color: d.status === 'completed' ? COLORS.green : d.status === 'failed' ? COLORS.red : COLORS.yellow }}>{d.status}</td>
                <td style={td}>{d.progress}%</td>
                <td style={td}>{d.size_bytes > 0 ? `${(d.size_bytes / 1024 / 1024).toFixed(1)} MB` : '-'}</td>
                <td style={td}>{d.speed_bps > 0 ? `${(d.speed_bps / 1024).toFixed(0)} KB/s` : '-'}</td>
              </tr>
            ))}
            {downloads.length === 0 && <tr><td style={td} colSpan={5}>No downloads</td></tr>}
          </tbody>
        </table>
      </Section>

      <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
        <div style={{ background: COLORS.surface, borderRadius: 8, padding: 12, flex: 1, border: `1px solid ${COLORS.border}` }}>
          <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>Battery</div>
          <div style={{ fontSize: 14, color: COLORS.cyan }}>{pwrStats.battery_percent != null ? `${pwrStats.battery_percent}%` : 'N/A'}</div>
          <div style={{ fontSize: 11, color: COLORS.muted }}>{pwrStats.ac_power ? 'AC Power' : 'Battery'} | {pwrStats.has_battery ? 'Has Battery' : 'No Battery'}</div>
        </div>
        <div style={{ background: COLORS.surface, borderRadius: 8, padding: 12, flex: 1, border: `1px solid ${COLORS.border}` }}>
          <div style={{ fontSize: 11, color: COLORS.muted, marginBottom: 4 }}>Download Dir</div>
          <div style={{ fontSize: 12, color: COLORS.text }}>{dlStats.download_dir ?? '-'}</div>
          <div style={{ fontSize: 11, color: COLORS.muted }}>{dlStats.total_bytes_downloaded ? `${(dlStats.total_bytes_downloaded / 1024 / 1024).toFixed(1)} MB total` : '0 MB total'}</div>
        </div>
      </div>
    </div>
  );
}
