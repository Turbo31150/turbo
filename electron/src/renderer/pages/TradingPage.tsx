import React, { useState, useCallback } from 'react';
import { useTrading, TradingSignal } from '../hooks/useTrading';
import SignalsTable from '../components/trading/SignalsTable';
import PositionsTable from '../components/trading/PositionsTable';

const styles = {
  page: {
    padding: 20,
    fontFamily: 'Consolas, Courier New, monospace',
    height: '100%',
    overflowY: 'auto' as const,
  },
  summaryBar: {
    display: 'flex',
    gap: 16,
    marginBottom: 20,
    flexWrap: 'wrap' as const,
  },
  statCard: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 6,
    padding: '12px 20px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 4,
    minWidth: 160,
  },
  statLabel: {
    fontSize: 10,
    color: '#4a6a8a',
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  statValue: {
    fontSize: 22,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
  },
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
  },
  refreshBtn: {
    padding: '6px 14px',
    borderRadius: 4,
    border: '1px solid #1a2a3a',
    backgroundColor: '#0d1117',
    color: '#4a6a8a',
    fontSize: 11,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
    transition: 'all 0.2s ease',
  },
  sections: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 20,
  },
  section: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 8,
    padding: 16,
    overflowX: 'auto' as const,
  },
  errorBanner: {
    padding: '8px 14px',
    backgroundColor: 'rgba(255, 68, 68, 0.1)',
    border: '1px solid rgba(255, 68, 68, 0.25)',
    borderRadius: 6,
    color: '#ff4444',
    fontSize: 12,
    marginBottom: 16,
  },
  confirmOverlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  confirmModal: {
    backgroundColor: '#0d1117',
    border: '1px solid #1a2a3a',
    borderRadius: 8,
    padding: 24,
    minWidth: 300,
    fontFamily: 'Consolas, Courier New, monospace',
  },
  confirmTitle: {
    fontSize: 16,
    fontWeight: 'bold' as const,
    color: '#e0e0e0',
    marginBottom: 16,
  },
  confirmText: {
    fontSize: 12,
    color: '#4a6a8a',
    marginBottom: 20,
    lineHeight: 1.6,
  },
  confirmActions: {
    display: 'flex',
    gap: 10,
    justifyContent: 'flex-end',
  },
  confirmCancelBtn: {
    padding: '6px 16px',
    borderRadius: 4,
    border: '1px solid #1a2a3a',
    backgroundColor: 'transparent',
    color: '#4a6a8a',
    fontSize: 11,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
  },
  confirmExecBtn: {
    padding: '6px 16px',
    borderRadius: 4,
    border: '1px solid #00d4ff',
    backgroundColor: '#00d4ff',
    color: '#0a0e14',
    fontSize: 11,
    fontWeight: 'bold' as const,
    cursor: 'pointer',
    fontFamily: 'Consolas, Courier New, monospace',
  },
};

const responsiveStyles = `
@media (max-width: 900px) {
  .trading-sections {
    grid-template-columns: 1fr !important;
  }
}
`;

export default function TradingPage() {
  const { signals, positions, pnl, loading, error, executeSignal, closePosition, refreshTrading } = useTrading();
  const [confirmSignalId, setConfirmSignalId] = useState<string | null>(null);

  const openPositions = positions.filter((p) => p.status === 'open');
  const pendingSignals = signals.filter((s) => s.status === 'pending');
  const pnlColor = pnl >= 0 ? '#00ff88' : '#ff4444';
  const pnlSign = pnl >= 0 ? '+' : '';

  // Find the signal being confirmed
  const confirmSignal = confirmSignalId ? signals.find((s) => s.id === confirmSignalId) : null;

  const handleExecute = useCallback((signalId: string) => {
    setConfirmSignalId(signalId);
  }, []);

  const confirmExecute = useCallback(() => {
    if (confirmSignalId) {
      executeSignal(confirmSignalId);
      setConfirmSignalId(null);
    }
  }, [confirmSignalId, executeSignal]);

  const handleClosePosition = useCallback((positionId: string) => {
    closePosition(positionId);
  }, [closePosition]);

  return (
    <>
      <style>{responsiveStyles}</style>
      <div style={styles.page}>
        <div style={styles.headerRow}>
          <div style={styles.title}>Trading</div>
          <button
            style={styles.refreshBtn}
            onClick={refreshTrading}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = '#00d4ff';
              e.currentTarget.style.color = '#00d4ff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#1a2a3a';
              e.currentTarget.style.color = '#4a6a8a';
            }}
          >
            {loading ? 'Chargement...' : 'Actualiser'}
          </button>
        </div>

        {/* Error banner */}
        {error && <div style={styles.errorBanner}>{error}</div>}

        {/* Summary bar */}
        <div style={styles.summaryBar}>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Positions Actives</span>
            <span style={{ ...styles.statValue, color: '#ffaa00' }}>{openPositions.length}</span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>PnL Total</span>
            <span style={{ ...styles.statValue, color: pnlColor }}>
              {pnlSign}${pnl.toFixed(2)}
            </span>
          </div>
          <div style={styles.statCard}>
            <span style={styles.statLabel}>Signaux en Attente</span>
            <span style={styles.statValue}>{pendingSignals.length}</span>
          </div>
        </div>

        {/* Tables */}
        <div className="trading-sections" style={styles.sections}>
          <div style={styles.section}>
            <SignalsTable signals={signals} onExecute={handleExecute} />
          </div>
          <div style={styles.section}>
            <PositionsTable positions={positions} onClose={handleClosePosition} />
          </div>
        </div>

        {/* Confirm modal */}
        {confirmSignal && (
          <div style={styles.confirmOverlay} onClick={() => setConfirmSignalId(null)}>
            <div style={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
              <div style={styles.confirmTitle}>Confirmer l'execution</div>
              <div style={styles.confirmText}>
                Executer le signal <strong style={{ color: '#e0e0e0' }}>{confirmSignal.pair}</strong>{' '}
                <span style={{ color: confirmSignal.direction === 'long' ? '#00ff88' : '#ff4444' }}>
                  {confirmSignal.direction.toUpperCase()}
                </span>{' '}
                avec un score de <strong style={{ color: '#e0e0e0' }}>{confirmSignal.score}/100</strong> ?
                <br />
                <span style={{ fontSize: 11 }}>
                  Prix d'entree: ${confirmSignal.entry_price.toLocaleString()} |
                  TP: ${confirmSignal.tp_price.toLocaleString()} |
                  SL: ${confirmSignal.sl_price.toLocaleString()}
                </span>
              </div>
              <div style={styles.confirmActions}>
                <button style={styles.confirmCancelBtn} onClick={() => setConfirmSignalId(null)}>
                  Annuler
                </button>
                <button style={styles.confirmExecBtn} onClick={confirmExecute}>
                  Executer
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
