import React, { useState, useEffect, useCallback } from 'react';
import { COLORS, FONT } from '../lib/theme';

const API = 'http://127.0.0.1:9742';

interface Job {
  job_id: string;
  name: string;
  action: string;
  interval_s: number;
  enabled: number;
  one_shot: number;
  last_run: number;
  run_count: number;
  last_result: string;
  last_error: string;
}

function Badge({ on }: { on: boolean }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
      backgroundColor: on ? COLORS.green + '22' : COLORS.red + '22',
      color: on ? COLORS.green : COLORS.red,
      border: `1px solid ${on ? COLORS.green + '44' : COLORS.red + '44'}`,
    }}>{on ? 'ACTIF' : 'INACTIF'}</span>
  );
}

export default function SchedulerPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});

  const refresh = useCallback(async () => {
    try {
      const [jRes, sRes] = await Promise.all([
        fetch(`${API}/api/scheduler/jobs`),
        fetch(`${API}/api/scheduler/stats`),
      ]);
      setJobs(await jRes.json());
      setStats(await sRes.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 8000); return () => clearInterval(t); }, [refresh]);

  const handleDelete = async (jobId: string) => {
    await fetch(`${API}/api/scheduler/jobs/${jobId}`, { method: 'DELETE' });
    refresh();
  };

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 20, fontFamily: FONT }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: COLORS.text, fontSize: 18, fontWeight: 700, margin: 0 }}>Planificateur</h2>
        <div style={{ display: 'flex', gap: 12 }}>
          {Object.entries(stats).filter(([k]) => k !== 'registered_handlers').map(([k, v]) => (
            <div key={k} style={{ textAlign: 'center' }}>
              <div style={{ color: COLORS.orange, fontSize: 16, fontWeight: 700 }}>{String(v)}</div>
              <div style={{ color: COLORS.textDim, fontSize: 9, textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      </div>

      {jobs.length === 0 ? (
        <div style={{
          backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8,
          padding: 30, textAlign: 'center', color: COLORS.textDim, fontSize: 13,
        }}>Aucun job planifie</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {jobs.map(job => (
            <div key={job.job_id} style={{
              backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: 14,
              display: 'flex', alignItems: 'center', gap: 14,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ color: COLORS.text, fontWeight: 600, fontSize: 13 }}>{job.name}</span>
                  <Badge on={!!job.enabled} />
                  {!!job.one_shot && (
                    <span style={{ fontSize: 9, color: COLORS.purple, fontWeight: 600 }}>ONE-SHOT</span>
                  )}
                </div>
                <div style={{ color: COLORS.textDim, fontSize: 11 }}>
                  Action: <span style={{ color: COLORS.orange }}>{job.action}</span>
                  {' | '}Interval: {job.interval_s}s
                  {' | '}Runs: {job.run_count}
                  {job.last_error && <span style={{ color: COLORS.red }}> | Erreur: {job.last_error}</span>}
                </div>
              </div>
              <button onClick={() => handleDelete(job.job_id)} style={{
                padding: '4px 10px', borderRadius: 4, fontSize: 10, cursor: 'pointer',
                backgroundColor: COLORS.red + '22', color: COLORS.red,
                border: `1px solid ${COLORS.red}44`,
              }}>Suppr</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
