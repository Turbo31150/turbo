import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactDOM from 'react-dom/client';

const WS_URL = 'ws://127.0.0.1:9742/ws';

// Get widget type from URL params
const params = new URLSearchParams(window.location.search);
const widgetType = params.get('type') || 'MiniCluster';

interface NodeInfo {
  name: string;
  status: string;
  latency_ms: number;
  models: string[];
  gpus?: number;
  vram_gb?: number;
}

interface Signal {
  id: string;
  pair: string;
  direction: string;
  score: number;
}

function MiniCluster() {
  const [nodes, setNodes] = useState<NodeInfo[]>([]);

  useEffect(() => {
    let ws: WebSocket;
    let disposed = false;
    const connect = () => {
      if (disposed) return;
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        ws.send(JSON.stringify({
          id: 'widget_cluster_1',
          type: 'request',
          channel: 'cluster',
          action: 'cluster_status',
          payload: {},
        }));
      };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.payload?.nodes) {
            setNodes(msg.payload.nodes);
          }
        } catch {}
      };
      ws.onclose = () => { if (!disposed) setTimeout(connect, 3000); };
    };
    connect();
    const interval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          id: `widget_cluster_${Date.now()}`,
          type: 'request',
          channel: 'cluster',
          action: 'cluster_status',
          payload: {},
        }));
      }
    }, 5000);
    return () => { disposed = true; ws?.close(); clearInterval(interval); };
  }, []);

  return (
    <div style={{ fontSize: 11 }}>
      {nodes.map(n => (
        <div key={n.name} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '3px 6px', borderBottom: '1px solid #1a2a3a',
        }}>
          <span style={{ color: '#e0e0e0', fontWeight: 'bold' }}>{n.name}</span>
          <span style={{
            color: n.status === 'online' ? '#10b981' : '#ef4444',
            fontSize: 9, textTransform: 'uppercase',
          }}>
            {n.status}
          </span>
          <span style={{ color: '#4a6a8a' }}>
            {n.latency_ms > 0 ? `${n.latency_ms}ms` : '—'}
          </span>
        </div>
      ))}
      {nodes.length === 0 && (
        <div style={{ color: '#4a6a8a', textAlign: 'center', padding: 16 }}>
          Connexion...
        </div>
      )}
    </div>
  );
}

function MiniTrading() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [pnl, setPnl] = useState(0);

  useEffect(() => {
    let ws: WebSocket;
    let disposed = false;
    const connect = () => {
      if (disposed) return;
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        ws.send(JSON.stringify({
          id: 'widget_trading_1',
          type: 'request',
          channel: 'trading',
          action: 'pending_signals',
          payload: {},
        }));
      };
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.payload?.signals) setSignals(msg.payload.signals.slice(0, 3));
          if (msg.payload?.total_pnl !== undefined) setPnl(msg.payload.total_pnl);
        } catch {}
      };
      ws.onclose = () => { if (!disposed) setTimeout(connect, 3000); };
    };
    connect();
    const interval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          id: `widget_trading_${Date.now()}`,
          type: 'request',
          channel: 'trading',
          action: 'pending_signals',
          payload: {},
        }));
      }
    }, 10000);
    return () => { disposed = true; ws?.close(); clearInterval(interval); };
  }, []);

  return (
    <div style={{ fontSize: 11 }}>
      <div style={{
        textAlign: 'center', padding: '4px 0', borderBottom: '1px solid #1a2a3a',
        color: pnl >= 0 ? '#10b981' : '#ef4444', fontWeight: 'bold',
      }}>
        PnL: {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} USDT
      </div>
      {signals.map(s => (
        <div key={s.id} style={{
          display: 'flex', justifyContent: 'space-between', padding: '3px 6px',
          borderBottom: '1px solid #1a2a3a',
        }}>
          <span>{s.pair.replace('/USDT:USDT', '')}</span>
          <span style={{ color: s.direction === 'LONG' ? '#10b981' : '#ef4444' }}>
            {s.direction}
          </span>
          <span style={{ color: '#00d4ff' }}>{s.score}</span>
        </div>
      ))}
    </div>
  );
}

function MiniVoice() {
  const [status, setStatus] = useState<'idle' | 'recording'>('idle');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let disposed = false;
    const connect = () => {
      if (disposed) return;
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.event === 'recording_started') setStatus('recording');
          if (msg.event === 'recording_stopped' || msg.event === 'transcription') setStatus('idle');
        } catch {}
      };
      ws.onclose = () => { wsRef.current = null; if (!disposed) setTimeout(connect, 3000); };
    };
    connect();
    return () => { disposed = true; ws?.close(); };
  }, []);

  const toggleRecording = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const action = status === 'recording' ? 'stop_recording' : 'start_recording';
    ws.send(JSON.stringify({
      id: `widget_voice_${Date.now()}`,
      type: 'request',
      channel: 'voice',
      action,
      payload: {},
    }));
    setStatus(status === 'recording' ? 'idle' : 'recording');
  }, [status]);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100%', fontSize: 12,
    }}>
      <div
        onClick={toggleRecording}
        style={{
          width: 40, height: 40, borderRadius: '50%',
          background: status === 'recording' ? '#ef4444' : '#1a2a3a',
          border: `2px solid ${status === 'recording' ? '#ef4444' : '#4a6a8a'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', transition: 'all 0.3s',
        }}>
        <span style={{ fontSize: 18 }}>&#x1F3A4;</span>
      </div>
      <span style={{ marginLeft: 8, color: status === 'recording' ? '#ef4444' : '#4a6a8a' }}>
        {status === 'recording' ? 'REC' : 'PTT'}
      </span>
    </div>
  );
}

const widgets: Record<string, React.FC> = {
  MiniCluster,
  MiniTrading,
  MiniVoice,
};

function WidgetApp() {
  const Widget = widgets[widgetType] || MiniCluster;

  return (
    <div className="widget-container">
      <div className="widget-header">
        <span className="widget-title">{widgetType}</span>
        <button className="widget-close" onClick={() => window.close()}>x</button>
      </div>
      <div className="widget-body">
        <Widget />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(<WidgetApp />);
