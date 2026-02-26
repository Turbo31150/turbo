import React, { useState, useEffect, useCallback, useRef, Suspense, lazy } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';

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

type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'lmstudio' | 'settings';

const PAGE_COMPONENTS: Record<Page, React.LazyExoticComponent<React.ComponentType>> = {
  dashboard: DashboardPage,
  chat: ChatPage,
  trading: TradingPage,
  voice: VoicePage,
  lmstudio: LMStudioPage,
  settings: SettingsPage,
};

const CSS = `
@keyframes toastIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
`;

const TOAST_COLORS = {
  error: { color: '#ef4444', bg: 'rgba(239,68,68,.12)', border: 'rgba(239,68,68,.3)' },
  warning: { color: '#f97316', bg: 'rgba(249,115,22,.12)', border: 'rgba(249,115,22,.3)' },
  info: { color: '#10b981', bg: 'rgba(16,185,129,.12)', border: 'rgba(16,185,129,.3)' },
};

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const { connected } = useWebSocket();
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
      setToasts(prev => prev.filter(t => Date.now() - t.timestamp < 4000));
    }, 4000);
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
    <>
      <style>{CSS}</style>
      <div style={{ display: 'flex', width: '100vw', height: '100vh', backgroundColor: '#0a0e14', overflow: 'hidden', fontFamily: 'Consolas, "Courier New", monospace' }}>
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <TopBar connected={connected} currentPage={currentPage} onDetach={handleDetach} />
          <main style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            <Suspense fallback={
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#6b7280', fontSize: 13, fontFamily: 'inherit' }}>
                Chargement...
              </div>
            }>
              <CurrentPageComponent />
            </Suspense>
          </main>
        </div>

        {toasts.length > 0 && (
          <div style={{ position: 'fixed', top: 50, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {toasts.map(t => {
              const c = TOAST_COLORS[t.type];
              return (
                <div key={t.id} style={{
                  padding: '8px 16px', borderRadius: 8, fontSize: 12, fontFamily: 'inherit',
                  color: c.color, backgroundColor: c.bg, border: `1px solid ${c.border}`,
                  backdropFilter: 'blur(8px)', animation: 'toastIn .3s ease',
                }}>
                  {t.message}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
