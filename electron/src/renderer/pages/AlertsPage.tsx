import React, { useState, useEffect, useCallback, memo } from 'react';
import { COLORS, FONT, FONTS } from '../lib/theme';

const API_BASE = 'http://127.0.0.1:9742';

const CSS = `
@keyframes alFade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.al-page::-webkit-scrollbar{width:5px}
.al-page::-webkit-scrollbar-thumb{background:${COLORS.border};border-radius:3px}
.al-card{animation:alFade .2s ease;transition:border-color .3s}
.al-btn{background:transparent;border:1px solid ${COLORS.border};color:${COLORS.text};padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px}
.al-btn:hover{border-color:${COLORS.orange};color:${COLORS.orange}}
.al-tab{padding:6px 14px;cursor:pointer;border-bottom:2px solid transparent;color:${COLORS.textDim};font-size:12px}
.al-tab.active{border-bottom-color:${COLORS.orange};color:${COLORS.orange}}
`;

interface Alert {
  id: string; key: string; message: string; level: string;
  source: string; created_at: number; updated_at: number;
  count: number; acknowledged: boolean; resolved: boolean;
}

interface DiagReport {
  grade: string; scores: Record<string, number>;
  problems: string[]; recommendations: string[];
}

const LEVEL_COLORS: Record<string, string> = {
  critical: COLORS.red, warning: COLORS.orange, info: COLORS.green,
};

const LevelBadge = memo(({ level }: { level: string }) => (
  <span style={{
    fontSize: 9, padding: '2px 6px', borderRadius: 3, fontWeight: 700,
    color: LEVEL_COLORS[level] || COLORS.text,
    background: `${LEVEL_COLORS[level] || COLORS.border}22`,
    border: `1px solid ${LEVEL_COLORS[level] || COLORS.border}44`,
    textTransform: 'uppercase',
  }}>{level}</span>
));

const fmtTs = (ts: number) => ts ? new Date(ts * 1000).toLocaleString('fr-FR') : '—';

export default function AlertsPage() {
  const [tab, setTab] = useState<'active' | 'diagnostic'>('active');
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [diagnostic, setDiagnostic] = useState<DiagReport | null>(null);
  const [stats, setStats] = useState<any>(null);

  const fetchData = useCallback(async () => {
    try {
      const [aRes, sRes] = await Promise.allSettled([
        fetch(`${API_BASE}/api/alerts/active`),
        fetch(`${API_BASE}/api/alerts/stats`),
      ]);
      if (aRes.status === 'fulfilled') {
        const d = await aRes.value.json();
        setAlerts(d.alerts || []);
      }
      if (sRes.status === 'fulfilled') setStats(await sRes.value.json());
    } catch {}
  }, []);

  const runDiagnostic = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/diagnostics/run`, { method: 'POST' });
      const d = await r.json();
      setDiagnostic(d);
    } catch {}
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => {
    const id = setInterval(fetchData, 5000);
    return () => clearInterval(id);
  }, [fetchData]);

  const handleAck = async (key: string) => {
    try {
      await fetch(`${API_BASE}/api/alerts/acknowledge`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      fetchData();
    } catch {}
  };

  const handleResolve = async (key: string) => {
    try {
      await fetch(`${API_BASE}/api/alerts/resolve`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      fetchData();
    } catch {}
  };

  const gradeColor = (g: string) =>
    g === 'A' ? COLORS.green : g === 'B' ? COLORS.green : g === 'C' ? COLORS.orange : COLORS.red;

  return (
    <div className="al-page" style={{
      height: '100%', overflow: 'auto', padding: 20,
      background: COLORS.bg, color: COLORS.text, fontFamily: FONTS.sans,
    }}>
      <style>{CSS}</style>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 20 }}>ALERTS</span>
        <span style={{ fontSize: 12, color: COLORS.textDim }}>
          {alerts.length} active · {stats?.total_alerts || 0} total
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="al-btn" onClick={fetchData}>Refresh</button>
          <button className="al-btn" onClick={runDiagnostic}>Run Diagnostic</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${COLORS.border}`, marginBottom: 12 }}>
        <div className={`al-tab ${tab === 'active' ? 'active' : ''}`} onClick={() => setTab('active')}>
          Active Alerts ({alerts.length})
        </div>
        <div className={`al-tab ${tab === 'diagnostic' ? 'active' : ''}`} onClick={() => setTab('diagnostic')}>
          Diagnostic {diagnostic ? `(${diagnostic.grade})` : ''}
        </div>
      </div>

      {tab === 'active' && (
        <>
          {alerts.length === 0 ? (
            <div style={{ textAlign: 'center', color: COLORS.textDim, padding: 40, fontSize: 13 }}>
              Aucune alerte active
            </div>
          ) : alerts.map(a => (
            <div key={a.key} className="al-card" style={{
              background: COLORS.bgCard, borderRadius: 6, padding: 12, marginBottom: 8,
              border: `1px solid ${LEVEL_COLORS[a.level] || COLORS.border}44`,
              borderLeft: `3px solid ${LEVEL_COLORS[a.level] || COLORS.border}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <LevelBadge level={a.level} />
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{a.message}</span>
                  </div>
                  <div style={{ fontSize: 10, color: COLORS.textDim }}>
                    source: {a.source || '—'} · count: {a.count} · {fmtTs(a.updated_at)}
                    {a.acknowledged && <span style={{ color: COLORS.orange }}> · ACK</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                  {!a.acknowledged && (
                    <button className="al-btn" onClick={() => handleAck(a.key)}
                      style={{ fontSize: 10 }}>ACK</button>
                  )}
                  <button className="al-btn" onClick={() => handleResolve(a.key)}
                    style={{ fontSize: 10, color: COLORS.green, borderColor: COLORS.green }}>Resolve</button>
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      {tab === 'diagnostic' && (
        <>
          {!diagnostic ? (
            <div style={{ textAlign: 'center', color: COLORS.textDim, padding: 40, fontSize: 13 }}>
              Cliquez "Run Diagnostic" pour analyser le cluster
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                <div style={{
                  width: 60, height: 60, borderRadius: '50%', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 28, fontWeight: 700,
                  color: gradeColor(diagnostic.grade),
                  border: `3px solid ${gradeColor(diagnostic.grade)}`,
                }}>{diagnostic.grade}</div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>Overall: {diagnostic.scores.overall}/100</div>
                  <div style={{ fontSize: 11, color: COLORS.textDim }}>
                    {Object.entries(diagnostic.scores).filter(([k]) => k !== 'overall')
                      .map(([k, v]) => `${k}: ${v}`).join(' · ')}
                  </div>
                </div>
              </div>

              {diagnostic.problems.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: COLORS.red, fontWeight: 600, marginBottom: 4 }}>PROBLEMS</div>
                  {diagnostic.problems.map((p, i) => (
                    <div key={i} style={{ fontSize: 12, color: COLORS.text, padding: '4px 0', borderBottom: `1px solid ${COLORS.border}22` }}>
                      {p}
                    </div>
                  ))}
                </div>
              )}

              {diagnostic.recommendations.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: COLORS.green, fontWeight: 600, marginBottom: 4 }}>RECOMMENDATIONS</div>
                  {diagnostic.recommendations.map((r, i) => (
                    <div key={i} style={{ fontSize: 12, color: COLORS.textDim, padding: '4px 0' }}>
                      {r}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
