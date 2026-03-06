/**
 * JARVIS Terminal Page v2 — Full-page terminal with cluster health indicator.
 */
import React, { useState, useEffect } from 'react';
import Terminal from '../components/Terminal';
import { COLORS, FONT } from '../lib/theme';
import { BACKEND_URL as API_BASE } from '../lib/config';

export default function TerminalPage() {
  const [health, setHealth] = useState<number | null>(null);
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    let active = true;
    const fetchHealth = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/cluster/dashboard`);
        if (r.ok) {
          const data = await r.json();
          if (active) {
            setHealth(data.health_score ?? null);
            const obs = data.observability?.alerts?.length ?? 0;
            const drift = data.drift?.alerts?.length ?? 0;
            setAlertCount(obs + drift);
          }
        }
      } catch { /* non-fatal */ }
    };
    fetchHealth();
    const timer = setInterval(fetchHealth, 15000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const healthColor = health === null ? COLORS.textDim
    : health >= 80 ? COLORS.green
    : health >= 50 ? COLORS.orange
    : COLORS.red;

  return (
    <div style={{
      padding: 20,
      fontFamily: FONT,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: COLORS.text, margin: 0 }}>
          Terminal
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {alertCount > 0 && (
            <span style={{
              fontSize: 10, color: COLORS.red, fontWeight: 600,
              padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(255, 80, 80, 0.15)',
            }}>
              {alertCount} alert{alertCount > 1 ? 's' : ''}
            </span>
          )}
          <span style={{
            fontSize: 10, color: healthColor, fontWeight: 600,
          }}>
            Health: {health !== null ? `${health}/100` : '...'}
          </span>
          <span style={{ fontSize: 10, color: COLORS.textDim }}>
            JARVIS CLI v10.6
          </span>
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <Terminal />
      </div>
    </div>
  );
}
