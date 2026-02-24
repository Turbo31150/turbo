import React from 'react';
import { TradingSignal } from '../../hooks/useTrading';

interface SignalsTableProps {
  signals: TradingSignal[];
  onExecute: (signalId: string) => void;
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
    color: '#00d4ff',
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
  directionBadge: {
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
  scoreBadge: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 3,
    fontSize: 11,
    fontWeight: 'bold' as const,
  },
  statusBadge: {
    display: 'inline-block',
    padding: '2px 6px',
    borderRadius: 3,
    fontSize: 9,
    fontWeight: 'bold' as const,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  },
  executeBtn: {
    padding: '4px 12px',
    borderRadius: 4,
    border: '1px solid #00d4ff',
    backgroundColor: 'transparent',
    color: '#00d4ff',
    fontSize: 10,
    fontWeight: 'bold' as const,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    transition: 'all 0.2s ease',
  },
  executeBtnDisabled: {
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

function getScoreColor(score: number): string {
  if (score >= 80) return '#00ff88';
  if (score >= 70) return '#ffaa00';
  return '#ff4444';
}

function getScoreBg(score: number): string {
  if (score >= 80) return 'rgba(0, 255, 136, 0.12)';
  if (score >= 70) return 'rgba(255, 170, 0, 0.12)';
  return 'rgba(255, 68, 68, 0.12)';
}

function getStatusStyle(status: TradingSignal['status']): React.CSSProperties {
  switch (status) {
    case 'pending': return { color: '#ffaa00', backgroundColor: 'rgba(255, 170, 0, 0.12)' };
    case 'executed': return { color: '#00ff88', backgroundColor: 'rgba(0, 255, 136, 0.12)' };
    case 'expired': return { color: '#4a6a8a', backgroundColor: '#1a2a3a' };
    case 'rejected': return { color: '#ff4444', backgroundColor: 'rgba(255, 68, 68, 0.12)' };
    default: return { color: '#4a6a8a', backgroundColor: '#1a2a3a' };
  }
}

function formatAge(timestamp: number): string {
  const now = Date.now();
  const diffMs = now - timestamp;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '<1m';
  if (diffMin < 60) return `${diffMin}m`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ${diffMin % 60}m`;
  return `${Math.floor(diffH / 24)}d`;
}

export default function SignalsTable({ signals, onExecute }: SignalsTableProps) {
  // Show only pending signals at the top, then recent executed ones
  const pendingSignals = signals.filter((s) => s.status === 'pending');
  const otherSignals = signals.filter((s) => s.status !== 'pending').slice(0, 10);
  const displaySignals = [...pendingSignals, ...otherSignals];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerIcon}>&#x25B2;</span>
        SIGNALS
        <span style={{ fontSize: 10, color: '#4a6a8a', fontWeight: 'normal' }}>
          ({pendingSignals.length} pending)
        </span>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Pair</th>
            <th style={styles.th}>Direction</th>
            <th style={styles.th}>Score</th>
            <th style={styles.th}>Price</th>
            <th style={styles.th}>Age</th>
            <th style={styles.th}>Status</th>
            <th style={styles.th}>Action</th>
          </tr>
        </thead>
        <tbody>
          {displaySignals.length === 0 ? (
            <tr>
              <td colSpan={7} style={styles.emptyRow}>
                Aucun signal actif
              </td>
            </tr>
          ) : (
            displaySignals.map((signal) => {
              const isLong = signal.direction === 'long';
              const canExecute = signal.status === 'pending';
              return (
                <tr key={signal.id}>
                  <td style={{ ...styles.td, fontWeight: 'bold', color: '#e0e0e0' }}>
                    {signal.pair}
                  </td>
                  <td style={styles.td}>
                    <span
                      style={{
                        ...styles.directionBadge,
                        ...(isLong ? styles.longBadge : styles.shortBadge),
                      }}
                    >
                      {signal.direction.toUpperCase()}
                    </span>
                  </td>
                  <td style={styles.td}>
                    <span
                      style={{
                        ...styles.scoreBadge,
                        color: getScoreColor(signal.score),
                        backgroundColor: getScoreBg(signal.score),
                      }}
                    >
                      {signal.score}
                    </span>
                  </td>
                  <td style={{ ...styles.td, color: '#4a6a8a' }}>
                    ${signal.entry_price.toLocaleString()}
                  </td>
                  <td style={{ ...styles.td, color: '#4a6a8a' }}>
                    {formatAge(signal.timestamp)}
                  </td>
                  <td style={styles.td}>
                    <span style={{ ...styles.statusBadge, ...getStatusStyle(signal.status) }}>
                      {signal.status}
                    </span>
                  </td>
                  <td style={styles.td}>
                    <button
                      style={{
                        ...styles.executeBtn,
                        ...(canExecute ? {} : styles.executeBtnDisabled),
                      }}
                      onClick={() => canExecute && onExecute(signal.id)}
                      disabled={!canExecute}
                      onMouseEnter={(e) => {
                        if (canExecute) {
                          e.currentTarget.style.backgroundColor = '#00d4ff';
                          e.currentTarget.style.color = '#0a0e14';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (canExecute) {
                          e.currentTarget.style.backgroundColor = 'transparent';
                          e.currentTarget.style.color = '#00d4ff';
                        }
                      }}
                    >
                      Execute
                    </button>
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
