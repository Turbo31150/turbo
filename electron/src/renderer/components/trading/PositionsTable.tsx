import React from 'react';
import { TradingPosition } from '../../hooks/useTrading';

interface PositionsTableProps {
  positions: TradingPosition[];
  onClose?: (positionId: string) => void;
}

const styles = {
  container: {
    fontFamily: 'Consolas, Courier New, monospace',
    width: '100%',
  },
  header: {
    fontSize: 14,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
    marginBottom: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  headerIcon: {
    color: '#ffaa00',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
  },
  th: {
    textAlign: 'left' as const,
    padding: '8px 12px',
    fontSize: 10,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    borderBottom: '1px solid #1a2a3a',
    fontWeight: 'normal' as const,
  },
  td: {
    padding: '10px 12px',
    fontSize: 12,
    color: '#e0e0e0',
    borderBottom: '1px solid #0d1117',
  },
  sideBadge: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 3,
    fontSize: 10,
    fontWeight: 'bold' as const,
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
  },
  longBadge: {
    color: '#00ff88',
    backgroundColor: 'rgba(0, 255, 136, 0.12)',
    border: '1px solid rgba(0, 255, 136, 0.25)',
  },
  shortBadge: {
    color: '#ff4444',
    backgroundColor: 'rgba(255, 68, 68, 0.12)',
    border: '1px solid rgba(255, 68, 68, 0.25)',
  },
  statusBadge: {
    display: 'inline-block',
    padding: '1px 5px',
    borderRadius: 3,
    fontSize: 9,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  },
  closeBtn: {
    padding: '4px 12px',
    borderRadius: 4,
    border: '1px solid #ff4444',
    backgroundColor: 'transparent',
    color: '#ff4444',
    fontSize: 10,
    fontWeight: 'bold' as const,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    transition: 'all 0.2s ease',
  },
  closeBtnDisabled: {
    opacity: 0.3,
    cursor: 'not-allowed' as const,
    borderColor: '#4a6a8a',
    color: '#4a6a8a',
  },
  emptyRow: {
    textAlign: 'center' as const,
    color: '#4a6a8a',
    padding: 24,
    fontSize: 12,
  },
};

function getStatusStyle(status: TradingPosition['status']): React.CSSProperties {
  switch (status) {
    case 'open': return { color: '#00ff88', backgroundColor: 'rgba(0, 255, 136, 0.12)' };
    case 'closed': return { color: '#4a6a8a', backgroundColor: '#1a2a3a' };
    case 'liquidated': return { color: '#ff4444', backgroundColor: 'rgba(255, 68, 68, 0.12)' };
    default: return { color: '#4a6a8a', backgroundColor: '#1a2a3a' };
  }
}

export default function PositionsTable({ positions, onClose }: PositionsTableProps) {
  const openPositions = positions.filter((p) => p.status === 'open');
  const closedPositions = positions.filter((p) => p.status !== 'open').slice(0, 5);
  const displayPositions = [...openPositions, ...closedPositions];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerIcon}>&#x25CF;</span>
        POSITIONS
        <span style={{ fontSize: 10, color: '#4a6a8a', fontWeight: 'normal' }}>
          ({openPositions.length} open)
        </span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Pair</th>
            <th style={styles.th}>Side</th>
            <th style={styles.th}>Entry</th>
            <th style={styles.th}>Current</th>
            <th style={styles.th}>PnL%</th>
            <th style={styles.th}>TP</th>
            <th style={styles.th}>SL</th>
            <th style={styles.th}>Action</th>
          </tr>
        </thead>
        <tbody>
          {displayPositions.length === 0 ? (
            <tr>
              <td colSpan={8} style={styles.emptyRow}>
                Aucune position ouverte
              </td>
            </tr>
          ) : (
            displayPositions.map((pos) => {
              const isLong = pos.direction === 'long';
              const pnlColor = pos.pnl_pct >= 0 ? '#00ff88' : '#ff4444';
              const pnlSign = pos.pnl_pct >= 0 ? '+' : '';
              const canClose = pos.status === 'open';
              return (
                <tr key={pos.id} style={{ opacity: pos.status === 'open' ? 1 : 0.5 }}>
                  <td style={{ ...styles.td, fontWeight: 'bold', color: '#e0e0e0' }}>
                    {pos.pair}
                  </td>
                  <td style={styles.td}>
                    <span
                      style={{
                        ...styles.sideBadge,
                        ...(isLong ? styles.longBadge : styles.shortBadge),
                      }}
                    >
                      {pos.direction.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ ...styles.td, color: '#4a6a8a' }}>
                    ${pos.entry_price.toLocaleString()}
                  </td>
                  <td style={styles.td}>
                    ${pos.current_price.toLocaleString()}
                  </td>
                  <td style={{ ...styles.td, color: pnlColor, fontWeight: 'bold' }}>
                    {pnlSign}{pos.pnl_pct.toFixed(2)}%
                    <div style={{ fontSize: 9, color: pnlColor, opacity: 0.7 }}>
                      {pnlSign}${pos.pnl.toFixed(2)}
                    </div>
                  </td>
                  <td style={{ ...styles.td, color: '#00ff88', fontSize: 11 }}>
                    ${pos.tp_price.toLocaleString()}
                  </td>
                  <td style={{ ...styles.td, color: '#ff4444', fontSize: 11 }}>
                    ${pos.sl_price.toLocaleString()}
                  </td>
                  <td style={styles.td}>
                    {onClose && (
                      <button
                        style={{
                          ...styles.closeBtn,
                          ...(canClose ? {} : styles.closeBtnDisabled),
                        }}
                        onClick={() => canClose && onClose(pos.id)}
                        disabled={!canClose}
                        onMouseEnter={(e) => {
                          if (canClose) {
                            e.currentTarget.style.backgroundColor = '#ff4444';
                            e.currentTarget.style.color = '#ffffff';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (canClose) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.color = '#ff4444';
                          }
                        }}
                      >
                        Close
                      </button>
                    )}
                    {!onClose && (
                      <span style={{ ...styles.statusBadge, ...getStatusStyle(pos.status) }}>
                        {pos.status}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
