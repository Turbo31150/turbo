import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface ResourceSnap {
  ts: number;
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  ram_percent: number;
  gpus: Array<{
    index: number; name: string; temp_c: number;
    vram_used_mb: number; vram_total_mb: number; utilization_percent: number;
  }>;
  disks: Array<{ mount: string; total_gb: number; used_gb: number; percent: number }>;
}

function ProgressBar({ value, color, label }: { value: number; color: string; label: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: COLORS.textDim, marginBottom: 3 }}>
        <span>{label}</span><span style={{ color }}>{value.toFixed(1)}%</span>
      </div>
      <div style={{ height: 6, backgroundColor: COLORS.border, borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${Math.min(value, 100)}%`, height: '100%', backgroundColor: color,
          borderRadius: 3, transition: 'width 0.5s ease',
        }} />
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`,
      borderRadius: 8, padding: 16,
    }}>
      <h3 style={{ color: COLORS.text, fontSize: 13, fontWeight: 700, margin: '0 0 12px 0' }}>{title}</h3>
      {children}
    </div>
  );
}

export default function ResourcePage() {
  const [snap, setSnap] = useState<ResourceSnap | null>(null);
  const [auto, setAuto] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/resources/sample`);
      setSnap(await r.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    refresh();
    if (!auto) return;
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh, auto]);

  const cpuColor = (snap?.cpu_percent ?? 0) > 80 ? COLORS.red : (snap?.cpu_percent ?? 0) > 50 ? COLORS.orange : COLORS.green;
  const ramColor = (snap?.ram_percent ?? 0) > 85 ? COLORS.red : (snap?.ram_percent ?? 0) > 60 ? COLORS.orange : COLORS.green;

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 20, fontFamily: FONT }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: COLORS.text, fontSize: 18, fontWeight: 700, margin: 0 }}>Resources Systeme</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setAuto(!auto)} style={{
            padding: '6px 12px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
            backgroundColor: auto ? COLORS.green + '22' : COLORS.border,
            color: auto ? COLORS.green : COLORS.textDim, border: `1px solid ${auto ? COLORS.green + '44' : COLORS.border}`,
          }}>{auto ? 'Auto ON' : 'Auto OFF'}</button>
          <button onClick={refresh} style={{
            padding: '6px 12px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
            backgroundColor: COLORS.orange, color: '#fff', border: 'none',
          }}>Rafraichir</button>
        </div>
      </div>

      {!snap ? (
        <p style={{ color: COLORS.textDim, fontSize: 13, textAlign: 'center' }}>Chargement...</p>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginBottom: 16 }}>
            <Card title="CPU">
              <ProgressBar value={snap.cpu_percent} color={cpuColor} label="Utilisation" />
            </Card>
            <Card title="RAM">
              <ProgressBar value={snap.ram_percent} color={ramColor} label={`${snap.ram_used_gb} / ${snap.ram_total_gb} GB`} />
            </Card>
          </div>

          {snap.gpus.length > 0 && (
            <>
              <h3 style={{ color: COLORS.text, fontSize: 14, fontWeight: 700, marginBottom: 8 }}>GPUs</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginBottom: 16 }}>
                {snap.gpus.map(gpu => {
                  const vramPct = gpu.vram_total_mb > 0 ? (gpu.vram_used_mb / gpu.vram_total_mb) * 100 : 0;
                  const tempColor = gpu.temp_c > 80 ? COLORS.red : gpu.temp_c > 65 ? COLORS.orange : COLORS.green;
                  return (
                    <Card key={gpu.index} title={`GPU ${gpu.index}: ${gpu.name}`}>
                      <ProgressBar value={gpu.utilization_percent} color={COLORS.purple} label="Utilisation GPU" />
                      <ProgressBar value={vramPct} color={COLORS.orange} label={`VRAM ${gpu.vram_used_mb.toFixed(0)}/${gpu.vram_total_mb.toFixed(0)} MB`} />
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
                        <span style={{ color: tempColor, fontSize: 18, fontWeight: 700 }}>{gpu.temp_c}°C</span>
                        <span style={{ color: COLORS.textDim, fontSize: 10 }}>Temperature</span>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}

          {snap.disks.length > 0 && (
            <>
              <h3 style={{ color: COLORS.text, fontSize: 14, fontWeight: 700, marginBottom: 8 }}>Disques</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {snap.disks.map(disk => (
                  <Card key={disk.mount} title={disk.mount}>
                    <ProgressBar value={disk.percent} color={disk.percent > 90 ? COLORS.red : COLORS.green}
                      label={`${disk.used_gb} / ${disk.total_gb} GB`} />
                  </Card>
                ))}
              </div>
            </>
          )}

          <div style={{ color: COLORS.textDim, fontSize: 10, marginTop: 12, textAlign: 'right' }}>
            MAJ: {new Date(snap.ts * 1000).toLocaleTimeString('fr-FR')}
          </div>
        </>
      )}
    </div>
  );
}
