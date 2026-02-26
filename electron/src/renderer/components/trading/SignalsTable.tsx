import React from 'react';
import { TradingSignal } from '../../hooks/useTrading';

interface SignalsTableProps {
  signals: TradingSignal[];
  onExecute: (signalId: string) => void;
}

const S = {
  container: { fontFamily: 'Consolas, "Courier New", monospace', width: '100%' } as React.CSSProperties,
  header: { fontSize: 14, fontWeight: 700, color: '#e0e0e0', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 } as React.CSSProperties,
  headerIcon: { color: '#f97316' } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse' } as React.CSSProperties,
  th: { textAlign: 'left', padding: '8px 12px', fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, borderBottom: '1px solid #1a2a3a', fontWeight: 400 } as React.CSSProperties,
  td: { padding: '10px 12px', fontSize: 12, color: '#e0e0e0', borderBottom: '1px solid #0d1117' } as React.CSSProperties,
  dirBadge: { display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' } as React.CSSProperties,
  longBadge: { color: '#10b981', backgroundColor: 'rgba(16,185,129,.12)', border: '1px solid rgba(16,185,129,.25)' },
  shortBadge: { color: '#ef4444', backgroundColor: 'rgba(239,68,68,.12)', border: '1px solid rgba(239,68,68,.25)' },
  scoreBadge: { display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700 } as React.CSSProperties,
  statusBadge: { display: 'inline-block', padding: '2px 6px', borderRadius: 4, fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: .5 } as React.CSSProperties,
  execBtn: { padding: '4px 12px', borderRadius: 4, border: '1px solid #f97316', backgroundColor: 'rgba(249,115,22,.08)', color: '#f97316', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', textTransform: 'uppercase', letterSpacing: 1, transition: 'all .2s' } as React.CSSProperties,
  execDisabled: { opacity: .3, cursor: 'not-allowed', borderColor: '#6b7280', color: '#6b7280' },
  empty: { textAlign: 'center', color: '#6b7280', padding: 24, fontSize: 12 } as React.CSSProperties,
};

function getScoreStyle(score: number) {
  if (score >= 80) return { color: '#10b981', backgroundColor: 'rgba(16,185,129,.12)' };
  if (score >= 70) return { color: '#f97316', backgroundColor: 'rgba(249,115,22,.12)' };
  return { color: '#ef4444', backgroundColor: 'rgba(239,68,68,.12)' };
}

function getStatusStyle(status: TradingSignal['status']): React.CSSProperties {
  switch (status) {
    case 'pending': return { color: '#f97316', backgroundColor: 'rgba(249,115,22,.12)' };
    case 'executed': return { color: '#10b981', backgroundColor: 'rgba(16,185,129,.12)' };
    case 'expired': return { color: '#6b7280', backgroundColor: '#1a2a3a' };
    case 'rejected': return { color: '#ef4444', backgroundColor: 'rgba(239,68,68,.12)' };
    default: return { color: '#6b7280', backgroundColor: '#1a2a3a' };
  }
}

function formatAge(timestamp: number): string {
  const diffMin = Math.floor((Date.now() - timestamp) / 60000);
  if (diffMin < 1) return '<1m';
  if (diffMin < 60) return `${diffMin}m`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ${diffMin % 60}m`;
  return `${Math.floor(diffH / 24)}d`;
}

export default function SignalsTable({ signals, onExecute }: SignalsTableProps) {
  const pending = signals.filter(s => s.status === 'pending');
  const others = signals.filter(s => s.status !== 'pending').slice(0, 10);
  const display = [...pending, ...others];

  return (
    <div style={S.container}>
      <div style={S.header}>
        <span style={S.headerIcon}>{'\u25B2'}</span>
        SIGNALS
        <span style={{ fontSize: 10, color: '#6b7280', fontWeight: 400 }}>({pending.length} pending)</span>
      </div>
      <table style={S.table}>
        <thead>
          <tr>{['Pair', 'Direction', 'Score', 'Price', 'Age', 'Status', 'Action'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {display.length === 0 ? (
            <tr><td colSpan={7} style={S.empty}>Aucun signal actif</td></tr>
          ) : display.map(sig => {
            const canExec = sig.status === 'pending';
            return (
              <tr key={sig.id}>
                <td style={{ ...S.td, fontWeight: 700 }}>{sig.pair}</td>
                <td style={S.td}>
                  <span style={{ ...S.dirBadge, ...(sig.direction === 'long' ? S.longBadge : S.shortBadge) }}>{sig.direction.toUpperCase()}</span>
                </td>
                <td style={S.td}>
                  <span style={{ ...S.scoreBadge, ...getScoreStyle(sig.score) }}>{sig.score}</span>
                </td>
                <td style={{ ...S.td, color: '#6b7280' }}>${sig.entry_price.toLocaleString()}</td>
                <td style={{ ...S.td, color: '#6b7280' }}>{formatAge(sig.timestamp)}</td>
                <td style={S.td}>
                  <span style={{ ...S.statusBadge, ...getStatusStyle(sig.status) }}>{sig.status}</span>
                </td>
                <td style={S.td}>
                  <button style={{ ...S.execBtn, ...(canExec ? {} : S.execDisabled) }}
                    onClick={() => canExec && onExecute(sig.id)} disabled={!canExec}>
                    Execute
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
