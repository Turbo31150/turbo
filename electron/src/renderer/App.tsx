import React, { useState, useEffect, useCallback, useRef, Suspense, lazy } from 'react';
import { useWebSocket, WsMessage } from './hooks/useWebSocket';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import ErrorBoundary from './components/ErrorBoundary';
import CommandPalette from './components/CommandPalette';
import { ClusterProvider } from './hooks/ClusterContext';
import type { Page } from './lib/types';
import { COLORS, FONT, applyTheme, getStoredTheme } from './lib/theme';

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
const OrchestratorPage = lazy(() => import('./pages/OrchestratorPage'));
const MemoryPage = lazy(() => import('./pages/MemoryPage'));
const MetricsPage = lazy(() => import('./pages/MetricsPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const WorkflowPage = lazy(() => import('./pages/WorkflowPage'));
const HealthPage = lazy(() => import('./pages/HealthPage'));
const ResourcePage = lazy(() => import('./pages/ResourcePage'));
const SchedulerPage = lazy(() => import('./pages/SchedulerPage'));
const ServicesPage = lazy(() => import('./pages/ServicesPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const QueuePage = lazy(() => import('./pages/QueuePage'));
const GatewayPage = lazy(() => import('./pages/GatewayPage'));
const InfraPage = lazy(() => import('./pages/InfraPage'));
const MeshPage = lazy(() => import('./pages/MeshPage'));
const AutomationPage = lazy(() => import('./pages/AutomationPage'));
const ProcessesPage = lazy(() => import('./pages/ProcessesPage'));
const SnapshotsPage = lazy(() => import('./pages/SnapshotsPage'));
const SystemPage = lazy(() => import('./pages/SystemPage'));
const TerminalPage = lazy(() => import('./pages/TerminalPage'));

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
  orchestrator: OrchestratorPage,
  memory: MemoryPage,
  metrics: MetricsPage,
  alerts: AlertsPage,
  workflows: WorkflowPage,
  health: HealthPage,
  resources: ResourcePage,
  scheduler: SchedulerPage,
  services: ServicesPage,
  notifications: NotificationsPage,
  queue: QueuePage,
  gateway: GatewayPage,
  infra: InfraPage,
  mesh: MeshPage,
  automation: AutomationPage,
  processes: ProcessesPage,
  snapshots: SnapshotsPage,
  system: SystemPage,
  terminal: TerminalPage,
};

const CSS = `
@keyframes toastIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}
`;

const TOAST_STYLES = {
  error: { color: COLORS.red, bg: COLORS.redAlpha(.12), border: COLORS.redAlpha(.3) },
  warning: { color: COLORS.orange, bg: COLORS.orangeAlpha(.12), border: COLORS.orangeAlpha(.3) },
  info: { color: COLORS.green, bg: COLORS.greenAlpha(.12), border: COLORS.greenAlpha(.3) },
};

function addToast(setToasts: React.Dispatch<React.SetStateAction<Toast[]>>, idRef: React.MutableRefObject<number>, message: string, type: Toast['type']) {
  setToasts(prev => [...prev, { id: ++idRef.current, message, type, timestamp: Date.now() }]);
}

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const { connected, subscribe } = useWebSocket();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [showPalette, setShowPalette] = useState(false);
  const toastIdRef = useRef(0);
  const prevConnected = useRef(connected);

  // Apply stored theme on mount
  useEffect(() => { applyTheme(getStoredTheme()); }, []);

  // Ctrl+K / Cmd+K to open command palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowPalette(v => !v);
      }
      if (e.key === 'Escape') setShowPalette(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

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

  const hasToasts = toasts.length > 0;
  useEffect(() => {
    if (!hasToasts) return;
    const timer = setInterval(() => {
      setToasts(prev => {
        const alive = prev.filter(t => Date.now() - t.timestamp < 5000);
        return alive.length === prev.length ? prev : alive;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [hasToasts]);

  useEffect(() => {
    const api = window.electronAPI;
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
        addToast(setToasts, toastIdRef, `Trade ${String(p.direction || '').toUpperCase()} ${String(p.pair || '')} execute`, 'info');
      }
      if (msg.event === 'position_closed') {
        const p = msg.payload || {};
        const pnl = Number(p.pnl) || 0;
        addToast(setToasts, toastIdRef, `Position fermee ${String(p.pair || '')}: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} USDT`, pnl >= 0 ? 'info' : 'warning');
      }
    }));

    unsubs.push(subscribe('system', (msg: WsMessage) => {
      if (msg.event === 'error' || msg.event === 'critical_error') {
        addToast(setToasts, toastIdRef, String(msg.payload?.message || 'Erreur systeme'), 'error');
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
    if (widgetType) window.electronAPI?.createWidget?.(widgetType);
  }, [currentPage]);

  const CurrentPageComponent = PAGE_COMPONENTS[currentPage];

  return (
    <ClusterProvider>
      <style>{CSS}</style>
      {showPalette && <CommandPalette onNavigate={setCurrentPage} onClose={() => setShowPalette(false)} />}
      <div style={{ display: 'flex', width: '100vw', height: '100vh', backgroundColor: COLORS.bg, overflow: 'hidden', fontFamily: FONT }}>
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <TopBar connected={connected} currentPage={currentPage} onDetach={handleDetach} />
          <main style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
            <ErrorBoundary key={currentPage}>
              <Suspense fallback={
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: COLORS.textDim, fontSize: 13, fontFamily: 'inherit' }}>
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
              const c = TOAST_STYLES[t.type];
              return (
                <div key={t.id} style={{
                  padding: '8px 16px', borderRadius: 8, fontSize: 12, fontFamily: 'inherit',
                  color: c.color, backgroundColor: c.bg, border: `1px solid ${c.border}`,
                  backdropFilter: 'blur(8px)', animation: 'toastIn .3s ease',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ flex: 1 }}>{t.message}</span>
                  <button aria-label="Fermer la notification" onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))} style={{
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
