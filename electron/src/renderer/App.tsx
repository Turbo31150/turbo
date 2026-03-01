import React, { useState, useEffect, useCallback, useRef, Suspense, lazy } from 'react';
import { useWebSocket, WsMessage } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import ErrorBoundary from './components/ErrorBoundary';
import { ClusterProvider } from './hooks/ClusterContext';
import type { Page } from './lib/types';

interface Toast {
  id: number;
  message: string;
  type: 'error' | 'warning' | 'info';
  timestamp: number;
}

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const TradingPage = lazy(() => import('./pages/TradingPage'));
const VoicePage = lazy(() => import('./pages/VoicePage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const LMStudioPage = lazy(() => import('./pages/LMStudioPage'));
const DictionaryPage = lazy(() => import('./pages/DictionaryPage'));
const PipelinePage = lazy(() => import('./pages/PipelinePage'));
const ToolboxPage = lazy(() => import('./pages/ToolboxPage'));
const LogsPage = lazy(() => import('./pages/LogsPage'));

const PAGE_COMPONENTS: Record<Page, React.LazyExoticComponent<React.ComponentType>> = {
  dashboard: DashboardPage,
  chat: ChatPage,
  trading: TradingPage,
  voice: VoicePage,
  lmstudio: LMStudioPage,
  settings: SettingsPage,
  dictionary: DictionaryPage,
  pipelines: PipelinePage,
  toolbox: ToolboxPage,
  logs: LogsPage,
};

const CSS = `
@keyframes toastIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
`;

const TOAST_COLORS = {
  error: { color: '#ef4444', bg: 'rgba(239,68,68,.12)', border: 'rgba(239,68,68,.3)' },
  warning: { color: '#f97316', bg: 'rgba(249,115,22,.12)', border: 'rgba(249,115,22,.3)' },
  info: { color: '#10b981', bg: 'rgba(16,185,129,.12)', border: 'rgba(16,185,129,.3)' },
};

function addToast(setToasts: React.Dispatch<React.SetStateAction<Toast[]>>, idRef: React.MutableRefObject<number>, message: string, type: Toast['type']) {
  setToasts(prev => [...prev, { id: ++idRef.current, message, type, timestamp: Date.now() }]);
}

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const { connected, subscribe } = useWebSocket();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);
  const prevConnected = useRef(connected);

  useEffect(() => {
    if (prevConnected.current && !connected) {
      const id = ++toastIdRef.current;
      setToasts(prev => [...prev, { id, message: 'Connexion WebSocket perdue', type: 'error', timestamp: Date.now() }]);
    } else if (!prevConnected.current && connected) {
      const id = ++toastIdRef.current;
      setToasts(prev => [...prev, { id, message: 'WebSocket reconnecte', type: 'info', timestamp: Date.now() }]);
    }
    prevConnected.current = connected;
  }, [connected]);

  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => Date.now() - t.timestamp < 5000));
    }, 5000);
    return () => clearTimeout(timer);
  }, [toasts]);

  useEffect(() => {
    const api = (window as any).electronAPI;
    if (api?.onNavigate) {
      const cleanup = api.onNavigate((page: string) => {
        if (page in PAGE_COMPONENTS) setCurrentPage(page as Page);
      });
      return cleanup;
    }
  }, []);

  // Subscribe to critical WS events for notifications
  useEffect(() => {
    const unsubs: (() => void)[] = [];

    unsubs.push(subscribe('cluster', (msg: WsMessage) => {
      if (msg.event === 'node_status_update' && msg.payload) {
        const { name, online } = msg.payload;
        if (online === false) {
          addToast(setToasts, toastIdRef, `Node ${name} OFFLINE`, 'error');
        }
      }
    }));

    unsubs.push(subscribe('trading', (msg: WsMessage) => {
      if (msg.event === 'signal_executed') {
        const p = msg.payload || {};
        addToast(setToasts, toastIdRef, `Trade ${p.direction?.toUpperCase() || ''} ${p.pair || ''} execute`, 'info');
      }
      if (msg.event === 'position_closed') {
        const p = msg.payload || {};
        const pnl = p.pnl ?? 0;
        addToast(setToasts, toastIdRef, `Position fermee ${p.pair || ''}: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} USDT`, pnl >= 0 ? 'info' : 'warning');
      }
    }));

    unsubs.push(subscribe('system', (msg: WsMessage) => {
      if (msg.event === 'error' || msg.event === 'critical_error') {
        addToast(setToasts, toastIdRef, msg.payload?.message || 'Erreur systeme', 'error');
      }
    }));

    return () => unsubs.forEach(u => u());
  }, [subscribe]);

  // Keyboard shortcuts: Ctrl+1..0 to navigate pages
  useEffect(() => {
    const PAGE_SHORTCUTS: Page[] = ['dashboard', 'chat', 'lmstudio', 'voice', 'dictionary', 'pipelines', 'toolbox', 'trading', 'logs', 'settings'];
    const handler = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.shiftKey || e.altKey) return;
      const num = parseInt(e.key);
      if (num >= 1 && num <= PAGE_SHORTCUTS.length) {
        e.preventDefault();
        setCurrentPage(PAGE_SHORTCUTS[num - 1]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const WIDGET_MAP: Record<string, string> = {
    dashboard: 'MiniCluster',
    trading: 'MiniTrading',
    voice: 'MiniVoice',
  };

  const handleDetach = useCallback(() => {
    const widgetType = WIDGET_MAP[currentPage];
    if (widgetType) (window as any).electronAPI?.createWidget?.(widgetType);
  }, [currentPage]);

  const CurrentPageComponent = PAGE_COMPONENTS[currentPage];

  return (
    <ClusterProvider>
      <style>{CSS}</style>
      <div style={{ display: 'flex', width: '100vw', height: '100vh', backgroundColor: '#0a0e14', overflow: 'hidden', fontFamily: 'Consolas, "Courier New", monospace' }}>
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <TopBar connected={connected} currentPage={currentPage} onDetach={handleDetach} />
          <main style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            <ErrorBoundary>
              <Suspense fallback={
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#6b7280', fontSize: 13, fontFamily: 'inherit' }}>
                  Chargement...
                </div>
              }>
                <CurrentPageComponent />
              </Suspense>
            </ErrorBoundary>
          </main>
        </div>

        {toasts.length > 0 && (
          <div role="status" aria-live="polite" style={{ position: 'fixed', top: 50, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {toasts.map(t => {
              const c = TOAST_COLORS[t.type];
              return (
                <div key={t.id} style={{
                  padding: '8px 16px', borderRadius: 8, fontSize: 12, fontFamily: 'inherit',
                  color: c.color, backgroundColor: c.bg, border: `1px solid ${c.border}`,
                  backdropFilter: 'blur(8px)', animation: 'toastIn .3s ease',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ flex: 1 }}>{t.message}</span>
                  <button onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))} style={{
                    background: 'none', border: 'none', color: c.color, cursor: 'pointer',
                    fontSize: 14, padding: 0, fontFamily: 'inherit', opacity: 0.6,
                  }}>{'\u2715'}</button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </ClusterProvider>
  );
}
