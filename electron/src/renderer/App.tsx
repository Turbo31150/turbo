import React, { useState, useEffect, useCallback, useRef, Suspense, lazy } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';

// Toast notification types
interface Toast {
  id: number;
  message: string;
  type: 'error' | 'warning' | 'info';
  timestamp: number;
}

// Lazy-load pages for better startup performance
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const TradingPage = lazy(() => import('./pages/TradingPage'));
const VoicePage = lazy(() => import('./pages/VoicePage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

// Page type
type Page = 'dashboard' | 'chat' | 'trading' | 'voice' | 'settings';

const PAGE_COMPONENTS: Record<Page, React.LazyExoticComponent<React.ComponentType>> = {
  dashboard: DashboardPage,
  chat: ChatPage,
  trading: TradingPage,
  voice: VoicePage,
  settings: SettingsPage,
};

const styles = {
  shell: {
    display: 'flex',
    width: '100vw',
    height: '100vh',
    backgroundColor: '#0a0e14',
    overflow: 'hidden',
    fontFamily: 'Consolas, Courier New, monospace',
  },
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    minWidth: 0,
  },
  content: {
    flex: 1,
    overflow: 'hidden',
    position: 'relative' as const,
  },
};

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const { connected } = useWebSocket();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);
  const prevConnected = useRef(connected);

  // Show toast on WS disconnect/reconnect
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

  // Auto-remove toasts after 4s
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => Date.now() - t.timestamp < 4000));
    }, 4000);
    return () => clearTimeout(timer);
  }, [toasts]);

  // Listen for navigation events from main process
  useEffect(() => {
    const api = (window as any).electronAPI;
    if (api?.onNavigate) {
      const cleanup = api.onNavigate((page: string) => {
        if (page in PAGE_COMPONENTS) {
          setCurrentPage(page as Page);
        }
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
    if (widgetType) {
      (window as any).electronAPI?.createWidget?.(widgetType);
    }
  }, [currentPage]);

  const CurrentPageComponent = PAGE_COMPONENTS[currentPage];

  return (
    <div style={styles.shell}>
      <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      <div style={styles.main}>
        <TopBar connected={connected} currentPage={currentPage} onDetach={handleDetach} />
        <main style={styles.content}>
          <Suspense fallback={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#4a6a8a', fontSize: 13, fontFamily: 'Consolas, Courier New, monospace' }}>
              Chargement...
            </div>
          }>
            <CurrentPageComponent />
          </Suspense>
        </main>
      </div>

      {/* Toast notifications */}
      {toasts.length > 0 && (
        <div style={{ position: 'fixed', top: 50, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {toasts.map(t => (
            <div
              key={t.id}
              style={{
                padding: '8px 16px',
                borderRadius: 6,
                fontSize: 12,
                fontFamily: 'Consolas, Courier New, monospace',
                color: t.type === 'error' ? '#ff4444' : t.type === 'warning' ? '#ffaa00' : '#00ff88',
                backgroundColor: t.type === 'error' ? 'rgba(255,68,68,0.12)' : t.type === 'warning' ? 'rgba(255,170,0,0.12)' : 'rgba(0,255,136,0.12)',
                border: `1px solid ${t.type === 'error' ? 'rgba(255,68,68,0.3)' : t.type === 'warning' ? 'rgba(255,170,0,0.3)' : 'rgba(0,255,136,0.3)'}`,
                backdropFilter: 'blur(8px)',
                animation: 'fadeIn 0.3s ease',
              }}
            >
              {t.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
