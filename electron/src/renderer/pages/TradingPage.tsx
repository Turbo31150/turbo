import React, { useState, useCallback, useMemo } from 'react';
import { useTrading, TradingSignal } from '../hooks/useTrading';

const CSS = `
@keyframes tFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.t-row{animation:tFadeIn .3s ease}
.t-row:hover{background:rgba(249,115,22,.03)!important}
.t-btn:hover{opacity:.85}
`;

const S = {
  page: { padding: 20, fontFamily: 'Consolas, "Courier New", monospace', height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: '#e0e0e0' } as React.CSSProperties,
  btn: { padding: '6px 14px', borderRadius: 6, border: '1px solid #2a3a4a', backgroundColor: 'transparent', color: '#6b7280', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  stats: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' } as React.CSSProperties,
  stat: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 8, padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140, flex: 1 } as React.CSSProperties,
  statLabel: { fontSize: 10, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5 } as React.CSSProperties,
  statVal: { fontSize: 24, fontWeight: 700 } as React.CSSProperties,
  section: { marginBottom: 24 } as React.CSSProperties,
  secTitle: { fontSize: 12, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 10 } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 } as React.CSSProperties,
  th: { textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid #1a2a3a', color: '#6b7280', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  td: { padding: '10px 12px', borderBottom: '1px solid #0d1117', color: '#e0e0e0' } as React.CSSProperties,
  long: { color: '#10b981', fontWeight: 700 },
  short: { color: '#ef4444', fontWeight: 700 },
  score: { display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700 } as React.CSSProperties,
  scoreHigh: { backgroundColor: 'rgba(16,185,129,.12)', color: '#10b981', border: '1px solid rgba(16,185,129,.25)' },
  scoreMed: { backgroundColor: 'rgba(249,115,22,.12)', color: '#f97316', border: '1px solid rgba(249,115,22,.25)' },
  scoreLow: { backgroundColor: 'rgba(239,68,68,.12)', color: '#ef4444', border: '1px solid rgba(239,68,68,.25)' },
  execBtn: { padding: '4px 12px', borderRadius: 4, border: 'none', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', textTransform: 'uppercase' } as React.CSSProperties,
  execLong: { backgroundColor: 'rgba(16,185,129,.15)', color: '#10b981' },
  execShort: { backgroundColor: 'rgba(239,68,68,.15)', color: '#ef4444' },
  pnl: (v: number) => ({ color: v >= 0 ? '#10b981' : '#ef4444', fontWeight: 700 }),
  closeBtn: { padding: '4px 10px', borderRadius: 4, border: '1px solid #2a3a4a', backgroundColor: 'transparent', color: '#6b7280', fontSize: 10, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties,
  empty: { textAlign: 'center', padding: 30, color: '#4b5563', fontSize: 12 } as React.CSSProperties,
  modal: { position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 } as React.CSSProperties,
  modalBox: { backgroundColor: '#0d1117', border: '1px solid #1a2a3a', borderRadius: 12, padding: 24, width: 380, fontFamily: 'inherit' } as React.CSSProperties,
};

export default function TradingPage() {
  const { signals, positions, pnl, loading, executeSignal, closePosition, refreshTrading } = useTrading();
  const [confirm, setConfirm] = useState<TradingSignal | null>(null);

  const activePositions = useMemo(() => positions.filter(p => p.status === 'open'), [positions]);
  const pendingSignals = useMemo(() => signals.filter(s => s.status === 'pending'), [signals]);

  const handleExec = useCallback(async () => {
    if (!confirm) return;
    await executeSignal(confirm.id);
    setConfirm(null);
  }, [confirm, executeSignal]);

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={S.header}>
          <span style={S.title}>Trading Terminal</span>
          <button style={S.btn} onClick={refreshTrading}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#f97316'; e.currentTarget.style.color = '#f97316'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#2a3a4a'; e.currentTarget.style.color = '#6b7280'; }}>
            {loading ? 'Actualisation...' : 'Actualiser'}
          </button>
        </div>

        {/* Stats */}
        <div style={S.stats}>
          <div style={S.stat}>
            <span style={S.statLabel}>Positions actives</span>
            <span style={{ ...S.statVal, color: activePositions.length > 0 ? '#f97316' : '#6b7280' }}>{activePositions.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>PnL Total</span>
            <span style={{ ...S.statVal, ...S.pnl(pnl) }}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} USDT</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Signaux en attente</span>
            <span style={{ ...S.statVal, color: '#c084fc' }}>{pendingSignals.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Win Rate</span>
            <span style={{ ...S.statVal, color: '#10b981' }}>---</span>
          </div>
        </div>

        {/* Signals */}
        <div style={S.section}>
          <div style={S.secTitle}>Signaux ({signals.length})</div>
          {signals.length === 0 ? (
            <div style={S.empty}>Aucun signal actif</div>
          ) : (
            <table style={S.table}>
              <thead>
                <tr>
                  {['Paire', 'Direction', 'Score', 'Entry', 'TP', 'SL', 'Status', ''].map(h => (
                    <th key={h} style={S.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signals.map(sig => (
                  <tr key={sig.id} className="t-row">
                    <td style={{ ...S.td, fontWeight: 700 }}>{sig.pair}</td>
                    <td style={{ ...S.td, ...(sig.direction === 'long' ? S.long : S.short) }}>{sig.direction.toUpperCase()}</td>
                    <td style={S.td}>
                      <span style={{ ...S.score, ...(sig.score >= 80 ? S.scoreHigh : sig.score >= 60 ? S.scoreMed : S.scoreLow) }}>
                        {sig.score}/100
                      </span>
                    </td>
                    <td style={S.td}>${sig.entry_price.toLocaleString()}</td>
                    <td style={{ ...S.td, color: '#10b981' }}>${sig.tp_price.toLocaleString()}</td>
                    <td style={{ ...S.td, color: '#ef4444' }}>${sig.sl_price.toLocaleString()}</td>
                    <td style={{ ...S.td, color: '#6b7280', textTransform: 'uppercase', fontSize: 10, letterSpacing: 1 }}>{sig.status}</td>
                    <td style={S.td}>
                      {sig.status === 'pending' && (
                        <button className="t-btn"
                          style={{ ...S.execBtn, ...(sig.direction === 'long' ? S.execLong : S.execShort) }}
                          onClick={() => setConfirm(sig)}>
                          EXEC
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Positions */}
        <div style={S.section}>
          <div style={S.secTitle}>Positions ({activePositions.length})</div>
          {activePositions.length === 0 ? (
            <div style={S.empty}>Aucune position ouverte</div>
          ) : (
            <table style={S.table}>
              <thead>
                <tr>
                  {['Paire', 'Dir', 'Entry', 'Current', 'PnL', 'Size', ''].map(h => (
                    <th key={h} style={S.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {activePositions.map(pos => (
                  <tr key={pos.id} className="t-row">
                    <td style={{ ...S.td, fontWeight: 700 }}>{pos.pair}</td>
                    <td style={{ ...S.td, ...(pos.direction === 'long' ? S.long : S.short) }}>{pos.direction.toUpperCase()}</td>
                    <td style={S.td}>${pos.entry_price.toLocaleString()}</td>
                    <td style={S.td}>${pos.current_price.toLocaleString()}</td>
                    <td style={{ ...S.td, ...S.pnl(pos.pnl) }}>
                      {pos.pnl >= 0 ? '+' : ''}{pos.pnl.toFixed(2)} ({pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%)
                    </td>
                    <td style={S.td}>{pos.size} USDT</td>
                    <td style={S.td}>
                      <button style={S.closeBtn} onClick={() => closePosition(pos.id)}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = '#ef4444'; e.currentTarget.style.color = '#ef4444'; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = '#2a3a4a'; e.currentTarget.style.color = '#6b7280'; }}>
                        CLOSE
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Confirm Modal */}
        {confirm && (
          <div style={S.modal} onClick={() => setConfirm(null)}>
            <div style={S.modalBox} onClick={e => e.stopPropagation()}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#e0e0e0', marginBottom: 16 }}>Confirmer execution</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: '#c0c0c0', marginBottom: 20 }}>
                <div>Paire: <strong style={{ color: '#e0e0e0' }}>{confirm.pair}</strong></div>
                <div>Direction: <strong style={confirm.direction === 'long' ? S.long : S.short}>{confirm.direction.toUpperCase()}</strong></div>
                <div>Entry: <strong style={{ color: '#e0e0e0' }}>${confirm.entry_price.toLocaleString()}</strong></div>
                <div>Score: <strong style={{ color: '#f97316' }}>{confirm.score}/100</strong></div>
              </div>
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button style={S.btn} onClick={() => setConfirm(null)}>Annuler</button>
                <button style={{ ...S.execBtn, ...(confirm.direction === 'long' ? S.execLong : S.execShort), padding: '8px 20px', fontSize: 12 }}
                  onClick={handleExec}>
                  EXECUTER {confirm.direction.toUpperCase()}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
