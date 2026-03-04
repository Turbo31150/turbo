import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface SubsystemStatus {
  [key: string]: unknown;
  error?: string;
}

interface HealthReport {
  ts: number;
  overall_health: number;
  status: string;
  subsystems: Record<string, SubsystemStatus>;
  problems: string[];
}

function GaugeCircle({ value, size = 120 }: { value: number; size?: number }) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (value / 100) * circ;
  const color = value >= 75 ? COLORS.green : value >= 40 ? COLORS.orange : COLORS.red;
  return (
    <svg width={size} height={size} style={{ display: 'block', margin: '0 auto' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={COLORS.border} strokeWidth={8} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={8}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round" transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
      <text x="50%" y="50%" textAnchor="middle" dy="0.35em"
        style={{ fill: color, fontSize: size * 0.28, fontWeight: 700, fontFamily: FONT }}>
        {value}
      </text>
    </svg>
  );
}

function SubsystemCard({ name, data }: { name: string; data: SubsystemStatus }) {
  const hasError = 'error' in data;
  return (
    <div style={{
      backgroundColor: COLORS.bgCard, border: `1px solid ${hasError ? COLORS.red + '44' : COLORS.border}`,
      borderRadius: 8, padding: 14,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: COLORS.text, fontWeight: 600, fontSize: 13, textTransform: 'capitalize' }}>{name.replace(/_/g, ' ')}</span>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          backgroundColor: hasError ? COLORS.red : COLORS.green,
        }} />
      </div>
      {hasError ? (
        <p style={{ color: COLORS.red, fontSize: 11, margin: 0 }}>{String(data.error)}</p>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {Object.entries(data).filter(([k]) => k !== 'error').map(([k, v]) => (
            <div key={k} style={{ textAlign: 'center', minWidth: 50 }}>
              <div style={{ color: COLORS.orange, fontSize: 14, fontWeight: 700 }}>{String(v)}</div>
              <div style={{ color: COLORS.textDim, fontSize: 9, textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function HealthPage() {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/health/full`);
      setReport(await r.json());
    } catch { setReport(null); }
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 15000); return () => clearInterval(t); }, [refresh]);

  const statusColor = report?.status === 'healthy' ? COLORS.green : report?.status === 'degraded' ? COLORS.orange : COLORS.red;

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 20, fontFamily: FONT }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 style={{ color: COLORS.text, fontSize: 18, fontWeight: 700, margin: 0 }}>Cluster Health</h2>
        <button onClick={refresh} disabled={loading} style={{
          padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600,
          backgroundColor: COLORS.orange, color: '#fff', border: 'none', cursor: 'pointer',
          opacity: loading ? 0.5 : 1,
        }}>Rafraichir</button>
      </div>

      {!report ? (
        <p style={{ color: COLORS.textDim, fontSize: 13, textAlign: 'center' }}>Chargement...</p>
      ) : (
        <>
          {/* Overall gauge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 30, marginBottom: 24 }}>
            <GaugeCircle value={report.overall_health} />
            <div>
              <div style={{
                fontSize: 20, fontWeight: 700, color: statusColor, textTransform: 'uppercase',
              }}>{report.status}</div>
              <div style={{ color: COLORS.textDim, fontSize: 12, marginTop: 4 }}>
                {report.problems.length} probleme(s) detecte(s)
              </div>
              <div style={{ color: COLORS.textDim, fontSize: 10, marginTop: 2 }}>
                Derniere MAJ: {new Date(report.ts * 1000).toLocaleTimeString('fr-FR')}
              </div>
            </div>
          </div>

          {/* Subsystems grid */}
          <h3 style={{ color: COLORS.text, fontSize: 14, fontWeight: 700, margin: '0 0 12px 0' }}>Sous-systemes</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10, marginBottom: 20 }}>
            {Object.entries(report.subsystems).map(([name, data]) => (
              <SubsystemCard key={name} name={name} data={data as SubsystemStatus} />
            ))}
          </div>

          {/* Problems */}
          {report.problems.length > 0 && (
            <>
              <h3 style={{ color: COLORS.red, fontSize: 14, fontWeight: 700, margin: '0 0 8px 0' }}>Problemes</h3>
              {report.problems.map((p, i) => (
                <div key={i} style={{
                  padding: '8px 12px', backgroundColor: `${COLORS.red}11`, border: `1px solid ${COLORS.red}33`,
                  borderRadius: 6, fontSize: 12, color: COLORS.red, marginBottom: 6,
                }}>{p}</div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
