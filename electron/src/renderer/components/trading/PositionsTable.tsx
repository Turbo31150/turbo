import React from 'react';
import { TradingPosition } from '../../hooks/useTrading';

interface PositionsTableProps {
  positions: TradingPosition[];
  onClose?: (positionId: string) => void;
}

const S = {
  container: { fontFamily: 'Consolas, "Courier New", monospace', width: '100%' } as React.CSSProperties,
  header: { fontSize: 14, fontWeight: 700, color: '#e0e0e0', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 } as React.CSSProperties,
  headerIcon: { color: '#f97316' } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse' } as React.CSSProperties,
  th: { textAlign: 'left', padding: '8px 12px', fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1, borderBottom: '1px solid #1a2a3a', fontWeight: 400 } as React.CSSProperties,
  td: { padding: '10px 12px', fontSize: 12, color: '#e0e0e0', borderBottom: '1px solid #0d1117' } as React.CSSProperties,
  sideBadge: { display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase' } as React.CSSProperties,
  longBadge: { color: '#10b981', backgroundColor: 'rgba(16,185,129,.12)', border: '1px solid rgba(16,185,129,.25)' },
  shortBadge: { color: '#ef4444', backgroundColor: 'rgba(239,68,68,.12)', border: '1px solid rgba(239,68,68,.25)' },
  statusBadge: { display: 'inline-block', padding: '1px 5px', borderRadius: 4, fontSize: 9, textTransform: 'uppercase', letterSpacing: .5 } as React.CSSProperties,
  closeBtn: { padding: '4px 12px', borderRadius: 4, border: '1px solid #ef4444', backgroundColor: 'transparent', color: '#ef4444', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', textTransform: 'uppercase', letterSpacing: 1, transition: 'all .2s' } as React.CSSProperties,
  closeDisabled: { opacity: .3, cursor: 'not-allowed', borderColor: '#6b7280', color: '#6b7280' },
  empty: { textAlign: 'center', color: '#6b7280', padding: 24, fontSize: 12 } as React.CSSProperties,
};

function getStatusStyle(status: TradingPosition['status']): React.CSSProperties {
  switch (status) {
    case 'open': return { color: '#10b981', backgroundColor: 'rgba(16,185,129,.12)' };
    case 'closed': return { color: '#6b7280', backgroundColor: '#1a2a3a' };
    case 'liquidated': return { color: '#ef4444', backgroundColor: 'rgba(239,68,68,.12)' };
    default: return { color: '#6b7280', backgroundColor: '#1a2a3a' };
  }
}

export default function PositionsTable({ positions, onClose }: PositionsTableProps) {
  const open = positions.filter(p => p.status === 'open');
  const closed = positions.filter(p => p.status !== 'open').slice(0, 5);
  const display = [...open, ...closed];

  return (
    <div style={S.container}>
      <div style={S.header}>
        <span style={S.headerIcon}>{'\u25CF'}</span>
        POSITIONS
        <span style={{ fontSize: 10, color: '#6b7280', fontWeight: 400 }}>({open.length} open)</span>
      </div>
      <table style={S.table}>
        <thead>
          <tr>{['Pair', 'Side', 'Entry', 'Current', 'PnL%', 'TP', 'SL', 'Action'].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {display.length === 0 ? (
            <tr><td colSpan={8} style={S.empty}>Aucune position ouverte</td></tr>
          ) : display.map(pos => {
            const pnlColor = pos.pnl_pct >= 0 ? '#10b981' : '#ef4444';
            const pnlSign = pos.pnl_pct >= 0 ? '+' : '';
            const canClose = pos.status === 'open';
            return (
              <tr key={pos.id} style={{ opacity: pos.status === 'open' ? 1 : .5 }}>
                <td style={{ ...S.td, fontWeight: 700 }}>{pos.pair}</td>
                <td style={S.td}>
                  <span style={{ ...S.sideBadge, ...(pos.direction === 'long' ? S.longBadge : S.shortBadge) }}>{pos.direction.toUpperCase()}</span>
                </td>
                <td style={{ ...S.td, color: '#6b7280' }}>${pos.entry_price.toLocaleString()}</td>
                <td style={S.td}>${pos.current_price.toLocaleString()}</td>
                <td style={{ ...S.td, color: pnlColor, fontWeight: 700 }}>
                  {pnlSign}{pos.pnl_pct.toFixed(2)}%
                  <div style={{ fontSize: 9, color: pnlColor, opacity: .7 }}>{pnlSign}${pos.pnl.toFixed(2)}</div>
                </td>
                <td style={{ ...S.td, color: '#10b981', fontSize: 11 }}>${pos.tp_price.toLocaleString()}</td>
                <td style={{ ...S.td, color: '#ef4444', fontSize: 11 }}>${pos.sl_price.toLocaleString()}</td>
                <td style={S.td}>
                  {onClose ? (
                    <button style={{ ...S.closeBtn, ...(canClose ? {} : S.closeDisabled) }}
                      onClick={() => canClose && onClose(pos.id)} disabled={!canClose}>
                      Close
                    </button>
                  ) : (
                    <span style={{ ...S.statusBadge, ...getStatusStyle(pos.status) }}>{pos.status}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
