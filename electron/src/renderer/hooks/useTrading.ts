import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocket, WsMessage } from './useWebSocket';

export interface TradingSignal {
  id: string;
  pair: string;
  direction: 'long' | 'short';
  score: number;
  entry_price: number;
  tp_price: number;
  sl_price: number;
  timestamp: number;
  status: 'pending' | 'executed' | 'expired' | 'rejected';
  agent?: string;
  reasoning?: string;
}

export interface TradingPosition {
  id: string;
  pair: string;
  direction: 'long' | 'short';
  entry_price: number;
  current_price: number;
  size: number;
  pnl: number;
  pnl_pct: number;
  tp_price: number;
  sl_price: number;
  timestamp: number;
  status: 'open' | 'closed' | 'liquidated';
}

interface TradingState {
  signals: TradingSignal[];
  positions: TradingPosition[];
  pnl: number;
  loading: boolean;
  error: string | null;
}

export function useTrading() {
  const [state, setState] = useState<TradingState>({
    signals: [],
    positions: [],
    pnl: 0,
    loading: true,
    error: null,
  });
  const { connected, request, subscribe } = useWebSocket();

  // Subscribe to trading channel events
  useEffect(() => {
    const unsub = subscribe('trading', (msg: WsMessage) => {
      switch (msg.event) {
        case 'signal_new': {
          const signal = msg.payload as TradingSignal;
          if (signal) {
            setState(prev => ({
              ...prev,
              signals: [signal, ...prev.signals].slice(0, 100), // Keep last 100
            }));
          }
          break;
        }

        case 'signal_update': {
          setState(prev => ({
            ...prev,
            signals: prev.signals.map(s =>
              s.id === msg.payload?.id ? { ...s, ...msg.payload } : s
            ),
          }));
          break;
        }

        case 'position_update': {
          const position = msg.payload as TradingPosition;
          if (position) {
            setState(prev => {
              const existingIdx = prev.positions.findIndex(p => p.id === position.id);
              let positions: TradingPosition[];
              if (existingIdx >= 0) {
                positions = [...prev.positions];
                positions[existingIdx] = { ...positions[existingIdx], ...position };
              } else {
                positions = [position, ...prev.positions];
              }

              // Recalculate total PnL from open positions
              const totalPnl = positions
                .filter(p => p.status === 'open')
                .reduce((sum, p) => sum + (p.pnl || 0), 0);

              return { ...prev, positions, pnl: totalPnl };
            });
          }
          break;
        }

        case 'position_closed': {
          setState(prev => ({
            ...prev,
            positions: prev.positions.map(p =>
              p.id === msg.payload?.id
                ? { ...p, status: 'closed' as const, ...msg.payload }
                : p
            ),
          }));
          break;
        }

        case 'pnl_update': {
          setState(prev => ({
            ...prev,
            pnl: msg.payload?.total_pnl ?? prev.pnl,
          }));
          break;
        }
      }
    });

    return unsub;
  }, [subscribe]);

  // Fetch signals
  const fetchSignals = useCallback(async () => {
    if (!connected) return;
    try {
      const response = await request('trading', 'get_signals');
      setState(prev => ({
        ...prev,
        signals: response.payload?.signals || [],
      }));
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        error: err.message,
      }));
    }
  }, [connected, request]);

  // Fetch positions
  const fetchPositions = useCallback(async () => {
    if (!connected) return;
    try {
      const response = await request('trading', 'get_positions');
      const positions = response.payload?.positions || [];
      const totalPnl = positions
        .filter((p: TradingPosition) => p.status === 'open')
        .reduce((sum: number, p: TradingPosition) => sum + (p.pnl || 0), 0);
      setState(prev => ({
        ...prev,
        positions,
        pnl: response.payload?.total_pnl ?? totalPnl,
      }));
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        error: err.message,
      }));
    }
  }, [connected, request]);

  // Execute a signal
  const executeSignal = useCallback(async (signalId: string) => {
    if (!connected) return;
    try {
      await request('trading', 'execute_signal', { signal_id: signalId });
      // Update will come via events
      setState(prev => ({
        ...prev,
        signals: prev.signals.map(s =>
          s.id === signalId ? { ...s, status: 'executed' as const } : s
        ),
      }));
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        error: err.message,
      }));
    }
  }, [connected, request]);

  // Close a position
  const closePosition = useCallback(async (positionId: string) => {
    if (!connected) return;
    try {
      await request('trading', 'close_position', { position_id: positionId });
      setState(prev => ({
        ...prev,
        positions: prev.positions.map(p =>
          p.id === positionId ? { ...p, status: 'closed' as const } : p
        ),
      }));
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        error: err.message,
      }));
    }
  }, [connected, request]);

  // Refresh all trading data
  const refreshTrading = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    await Promise.all([fetchSignals(), fetchPositions()]);
    setState(prev => ({ ...prev, loading: false }));
  }, [fetchSignals, fetchPositions]);

  const refreshRef = useRef(refreshTrading);
  refreshRef.current = refreshTrading;

  // Initial fetch
  useEffect(() => {
    if (connected) {
      refreshRef.current();
    } else {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [connected]);

  return {
    signals: state.signals,
    positions: state.positions,
    pnl: state.pnl,
    loading: state.loading,
    error: state.error,
    executeSignal,
    closePosition,
    refreshTrading,
  };
}
