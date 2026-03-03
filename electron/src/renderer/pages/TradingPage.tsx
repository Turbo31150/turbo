import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useTrading, TradingSignal } from '../hooks/useTrading';
import { useWebSocket, WsMessage } from '../hooks/useWebSocket';
import { COLORS, FONT } from '../lib/theme';

const CSS = `
@keyframes tFadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.t-row{animation:tFadeIn .3s ease}
.t-row:hover{background:${COLORS.orangeAlpha(0.03)}!important}
.t-btn:hover{opacity:.85}
`;

const S = {
  page: { padding: 20, fontFamily: FONT, height: '100%', overflowY: 'auto' } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 } as React.CSSProperties,
  title: { fontSize: 18, fontWeight: 700, color: COLORS.text } as React.CSSProperties,
  btn: { padding: '6px 14px', borderRadius: 6, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 11, cursor: 'pointer', fontFamily: 'inherit', transition: 'all .2s' } as React.CSSProperties,
  stats: { display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' } as React.CSSProperties,
  stat: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 140, flex: 1 } as React.CSSProperties,
  statLabel: { fontSize: 10, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1.5 } as React.CSSProperties,
  statVal: { fontSize: 24, fontWeight: 700 } as React.CSSProperties,
  section: { marginBottom: 24 } as React.CSSProperties,
  secTitle: { fontSize: 12, fontWeight: 700, color: COLORS.textDim, textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 10 } as React.CSSProperties,
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 } as React.CSSProperties,
  th: { textAlign: 'left', padding: '8px 12px', borderBottom: `1px solid ${COLORS.border}`, color: COLORS.textDim, fontSize: 10, textTransform: 'uppercase', letterSpacing: 1 } as React.CSSProperties,
  td: { padding: '10px 12px', borderBottom: `1px solid ${COLORS.bgCard}`, color: COLORS.text } as React.CSSProperties,
  long: { color: COLORS.green, fontWeight: 700 },
  short: { color: COLORS.red, fontWeight: 700 },
  score: { display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700 } as React.CSSProperties,
  scoreHigh: { backgroundColor: COLORS.greenAlpha(0.12), color: COLORS.green, border: `1px solid ${COLORS.greenAlpha(0.25)}` },
  scoreMed: { backgroundColor: COLORS.orangeAlpha(0.12), color: COLORS.orange, border: `1px solid ${COLORS.orangeAlpha(0.25)}` },
  scoreLow: { backgroundColor: COLORS.redAlpha(0.12), color: COLORS.red, border: `1px solid ${COLORS.redAlpha(0.25)}` },
  execBtn: { padding: '4px 12px', borderRadius: 4, border: 'none', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', textTransform: 'uppercase' } as React.CSSProperties,
  execLong: { backgroundColor: COLORS.greenAlpha(0.15), color: COLORS.green },
  execShort: { backgroundColor: COLORS.redAlpha(0.15), color: COLORS.red },
  pnl: (v: number) => ({ color: v >= 0 ? COLORS.green : COLORS.red, fontWeight: 700 }),
  closeBtn: { padding: '4px 10px', borderRadius: 4, border: `1px solid ${COLORS.border}`, backgroundColor: 'transparent', color: COLORS.textDim, fontSize: 10, cursor: 'pointer', fontFamily: 'inherit' } as React.CSSProperties,
  empty: { textAlign: 'center', padding: 30, color: COLORS.textDimmer, fontSize: 12 } as React.CSSProperties,
  modal: { position: 'fixed', inset: 0, backgroundColor: COLORS.overlay, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 } as React.CSSProperties,
  modalBox: { backgroundColor: COLORS.bgCard, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 24, width: 380, fontFamily: 'inherit' } as React.CSSProperties,
};

interface AlertItem { id: number; text: string; ts: number; type: 'signal' | 'exec' | 'close' | 'info' }

const ALERT_COLOR: Record<string, string> = { signal: COLORS.purple, exec: COLORS.green, close: COLORS.red, info: COLORS.textDim };

export default function TradingPage() {
  const { signals, positions, pnl, loading, error, executeSignal, closePosition, refreshTrading } = useTrading();
  const [confirm, setConfirm] = useState<TradingSignal | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const { subscribe } = useWebSocket();
  const alertIdRef = useRef(0);

  const activePositions = useMemo(() => positions.filter(p => p.status === 'open'), [positions]);
  const closedPositions = useMemo(() => positions.filter(p => p.status === 'closed'), [positions]);
  const pendingSignals = useMemo(() => signals.filter(s => s.status === 'pending'), [signals]);
  const winRate = useMemo(() => {
    if (closedPositions.length === 0) return null;
    const wins = closedPositions.filter(p => p.pnl >= 0).length;
    return Math.round((wins / closedPositions.length) * 100);
  }, [closedPositions]);

  useEffect(() => {
    const unsub = subscribe('trading', (msg: WsMessage) => {
      const text = msg.event || msg.action || JSON.stringify(msg.payload || {}).slice(0, 100);
      const type = msg.event?.includes('signal') ? 'signal' as const
        : msg.event?.includes('exec') ? 'exec' as const
        : msg.event?.includes('close') ? 'close' as const
        : 'info' as const;
      setAlerts(prev => [{ id: ++alertIdRef.current, text, ts: Date.now(), type }, ...prev].slice(0, 30));
    });
    return unsub;
  }, [subscribe]);

  // Escape to close confirm modal
  useEffect(() => {
    if (!confirm) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setConfirm(null); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [confirm]);

  const handleExec = useCallback(async () => {
    if (!confirm) return;
    try {
      await executeSignal(confirm.id);
    } catch (_e: unknown) {
      // Error already handled in useTrading state
    }
    setConfirm(null);
  }, [confirm, executeSignal]);

  const handleClose = useCallback(async (positionId: string) => {
    try {
      await closePosition(positionId);
    } catch (_e: unknown) {
      // Error already handled in useTrading state
    }
  }, [closePosition]);

  return (
    <>
      <style>{CSS}</style>
      <div style={S.page}>
        <div style={S.header}>
          <span style={S.title}>Trading Terminal</span>
          <button style={S.btn} onClick={refreshTrading}
            onMouseEnter={e => { e.currentTarget.style.borderColor = COLORS.orange; e.currentTarget.style.color = COLORS.orange; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = COLORS.border; e.currentTarget.style.color = COLORS.textDim; }}>
            {loading ? 'Actualisation...' : 'Actualiser'}
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div style={{
            padding: '8px 16px', borderRadius: 8, fontSize: 12, marginBottom: 12,
            fontFamily: 'inherit', backgroundColor: COLORS.redAlpha(0.08),
            border: `1px solid ${COLORS.redAlpha(0.25)}`, color: COLORS.red,
          }}>{error}</div>
        )}

        {/* Stats */}
        <div style={S.stats}>
          <div style={S.stat}>
            <span style={S.statLabel}>Positions actives</span>
            <span style={{ ...S.statVal, color: activePositions.length > 0 ? COLORS.orange : COLORS.textDim }}>{activePositions.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>PnL Total</span>
            <span style={{ ...S.statVal, ...S.pnl(pnl) }}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} USDT</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Signaux en attente</span>
            <span style={{ ...S.statVal, color: COLORS.purple }}>{pendingSignals.length}</span>
          </div>
          <div style={S.stat}>
            <span style={S.statLabel}>Win Rate</span>
            <span style={{ ...S.statVal, color: winRate !== null ? (winRate >= 50 ? COLORS.green : COLORS.red) : COLORS.textDim }}>
              {winRate !== null ? `${winRate}%` : '---'}
            </span>
            {closedPositions.length > 0 && (
              <span style={{ fontSize: 10, color: COLORS.textDim }}>{closedPositions.length} trades</span>
            )}
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
                    <td style={{ ...S.td, color: COLORS.green }}>${sig.tp_price.toLocaleString()}</td>
                    <td style={{ ...S.td, color: COLORS.red }}>${sig.sl_price.toLocaleString()}</td>
                    <td style={{ ...S.td, color: COLORS.textDim, textTransform: 'uppercase', fontSize: 10, letterSpacing: 1 }}>{sig.status}</td>
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
                      <button style={S.closeBtn} onClick={() => handleClose(pos.id)}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = COLORS.red; e.currentTarget.style.color = COLORS.red; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = COLORS.border; e.currentTarget.style.color = COLORS.textDim; }}>
                        CLOSE
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Alerts Feed */}
        {alerts.length > 0 && (
          <div style={S.section}>
            <div style={S.secTitle}>Alertes Live ({alerts.length})</div>
            <div role="log" aria-live="assertive" aria-label="Alertes trading" style={{ maxHeight: 160, overflowY: 'auto', backgroundColor: COLORS.bg, borderRadius: 8, border: `1px solid ${COLORS.border}`, padding: 8 }}>
              {alerts.map(a => (
                <div key={a.id} style={{ display: 'flex', gap: 8, padding: '4px 8px', fontSize: 11, color: COLORS.textMuted, borderBottom: `1px solid ${COLORS.border}30` }}>
                  <span style={{ fontSize: 10, color: COLORS.textDimmer, minWidth: 60, fontVariantNumeric: 'tabular-nums' }}>
                    {new Date(a.ts).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span style={{
                    fontSize: 9, fontWeight: 700, minWidth: 50, textTransform: 'uppercase', letterSpacing: 0.5,
                    color: ALERT_COLOR[a.type] || COLORS.textDim,
                  }}>{a.type}</span>
                  <span>{a.text}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Confirm Modal */}
        {confirm && (
          <div style={S.modal} onClick={() => setConfirm(null)} role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <div style={S.modalBox} onClick={e => e.stopPropagation()}>
              <div id="confirm-title" style={{ fontSize: 16, fontWeight: 700, color: COLORS.text, marginBottom: 16 }}>Confirmer execution</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: COLORS.textMuted, marginBottom: 20 }}>
                <div>Paire: <strong style={{ color: COLORS.text }}>{confirm.pair}</strong></div>
                <div>Direction: <strong style={confirm.direction === 'long' ? S.long : S.short}>{confirm.direction.toUpperCase()}</strong></div>
                <div>Entry: <strong style={{ color: COLORS.text }}>${confirm.entry_price.toLocaleString()}</strong></div>
                <div>Score: <strong style={{ color: COLORS.orange }}>{confirm.score}/100</strong></div>
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
